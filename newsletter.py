import os
import re
import json
import random
import smtplib
import requests
import feedparser
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import anthropic

from config import INTERESSES, EMAIL_DESTINO, EMAIL_REMETENTE

MODEL           = "claude-sonnet-4-5"
LOG             = "log.txt"
MAX_CANDIDATES  = 30    # limite enviado ao Claude
LOG_WINDOW_DAYS = 120   # dias de histórico passados ao Claude

FRASES = [
    "A vida não examinada não vale a pena ser vivida. — Sócrates",
    "Só sei que nada sei. — Sócrates",
    "O homem é a medida de todas as coisas. — Protágoras",
    "Conhece-te a ti mesmo. — Inscrição do Oráculo de Delfos",
    "A dúvida é o princípio da sabedoria. — Aristóteles",
    "O todo é maior que a soma das partes. — Aristóteles",
    "Penso, logo existo. — René Descartes",
    "O homem nasce livre, mas por toda parte encontra-se acorrentado. — Rousseau",
    "Age apenas segundo uma máxima tal que possas querer que ela se torne lei universal. — Kant",
    "Deus está morto. — Nietzsche",
    "O que não me mata, me fortalece. — Nietzsche",
    "Tornar-se o que se é. — Nietzsche",
    "A existência precede a essência. — Sartre",
    "O inferno são os outros. — Sartre",
    "Ser é ser percebido. — Berkeley",
    "O homem é o único animal que ri. — Aristóteles",
    "A imaginação é mais importante que o conhecimento. — Einstein",
    "A simplicidade é o último grau de sofisticação. — Leonardo da Vinci",
    "Não é a resposta que ilumina, mas a pergunta. — Ionesco",
    "A filosofia é um combate contra o enfeitiçamento do nosso entendimento. — Wittgenstein",
    "O silêncio é o mais perfeito heraldo da alegria. — Shakespeare",
    "Somos o que repetidamente fazemos. A excelência não é um ato, mas um hábito. — Aristóteles",
    "Prefiro morrer de paixão do que de tédio. — Van Gogh",
    "A liberdade não é ter o que se quer, mas querer o que se tem. — Epicteto",
    "Não chores pelo que perdeste. Sorri pelo que viveste. — García Márquez",
    "A maior glória não é nunca cair, mas levantar-se sempre. — Confúcio",
    "O caminho de mil léguas começa com um único passo. — Lao-Tsé",
    "Quando o sábio aponta a lua, o tolo olha para o dedo. — Provérbio Zen",
    "A mente que se abre a uma nova ideia jamais voltará ao seu tamanho original. — Einstein",
    "Aquele que tem um porquê para viver pode suportar quase qualquer como. — Nietzsche",
    "Em meio ao inverno, descobri em mim um verão invencível. — Camus",
    "O tempo que você gosta de desperdiçar não é desperdiçado. — Bertrand Russell",
    "A verdade raramente é pura e nunca é simples. — Oscar Wilde",
    "Para cada minuto de raiva, você perde sessenta segundos de felicidade. — Emerson",
    "A maior riqueza é a pobreza de desejos. — Sêneca",
    "Não é pobre quem tem pouco, mas quem deseja muito. — Sêneca",
    "Nenhum homem pode atravessar o mesmo rio duas vezes. — Heráclito",
    "O caráter de um homem é o seu destino. — Heráclito",
    "A arte de viver é mais parecida com a arte de lutar do que com a de dançar. — Marco Aurélio",
    "Você tem poder sobre sua mente, não sobre eventos externos. — Marco Aurélio",
    "A filosofia não promete nada externo ao homem. — Epicteto",
    "Aproveite o momento presente. — Horácio",
    "A sabedoria começa no espanto. — Sócrates",
    "O universo está em nós. Somos feitos de matéria estelar. — Carl Sagan",
    "Em algum lugar, algo incrível está esperando para ser descoberto. — Carl Sagan",
    "A ciência não é apenas um corpo de conhecimento, é uma forma de pensar. — Carl Sagan",
    "Não há vento favorável para quem não sabe para onde vai. — Sêneca",
    "Toda a nossa dignidade consiste no pensamento. — Pascal",
    "O coração tem razões que a própria razão desconhece. — Pascal",
    "A curiosidade é a mãe de todas as ciências. — Leonardo da Vinci",
]


# ── FETCH ──────────────────────────────────────────────────────────────────────

def fetch_hn():
    candidates = []
    for interesse in INTERESSES:
        try:
            url  = f"https://hn.algolia.com/api/v1/search?query={interesse}&tags=story&hitsPerPage=8"
            hits = requests.get(url, timeout=10).json().get("hits", [])
            for h in hits:
                if h.get("url") and h.get("title"):
                    candidates.append({
                        "titulo": h["title"],
                        "url":    h["url"],
                        "fonte":  "Hacker News",
                        "data":   h.get("created_at", "")[:10] or None,
                    })
        except Exception:
            continue
    return candidates


def fetch_arxiv():
    # só busca arXiv se o usuário tiver interesse em áreas técnicas/científicas
    tech_keywords = ["ia", "inteligência artificial", "machine learning", "ml",
                     "ciência", "tecnologia", "programação", "dados", "física", "matemática"]
    tem_interesse_tecnico = any(
        any(kw in i.lower() for kw in tech_keywords)
        for i in INTERESSES
    )
    if not tem_interesse_tecnico:
        return []

    candidates = []
    try:
        url  = (
            "https://export.arxiv.org/api/query"
            "?search_query=cat:cs.AI+OR+cat:cs.LG+OR+cat:cs.CL"
            "&sortBy=submittedDate&sortOrder=descending&max_results=15"
        )
        feed = feedparser.parse(url)
        for e in feed.entries:
            candidates.append({
                "titulo": e.title.replace("\n", " ").strip(),
                "url":    e.link,
                "fonte":  "arXiv",
                "data":   e.get("published", "")[:10] or None,
            })
    except Exception:
        pass
    return candidates


def fetch_google_news():
    candidates = []
    for interesse in INTERESSES:
        try:
            q    = interesse.replace(" ", "+")
            url  = f"https://news.google.com/rss/search?q={q}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
            feed = feedparser.parse(url)
            for e in feed.entries[:5]:
                candidates.append({
                    "titulo": e.title,
                    "url":    e.link,
                    "fonte":  "Google News",
                    "data":   e.get("published", "")[:10] or None,
                })
        except Exception:
            continue
    return candidates


def collect_candidates():
    raw  = fetch_hn() + fetch_arxiv() + fetch_google_news()
    seen, unique = set(), []
    for c in raw:
        if c["url"] not in seen:
            seen.add(c["url"])
            unique.append(c)
    # limita payload enviado ao Claude
    return unique[:MAX_CANDIDATES]


# ── LOG ────────────────────────────────────────────────────────────────────────

def load_log():
    if not os.path.exists(LOG):
        return ""
    corte = (datetime.now() - timedelta(days=LOG_WINDOW_DAYS)).strftime("%Y-%m-%d")
    linhas_recentes = []
    with open(LOG, "r", encoding="utf-8") as f:
        for linha in f:
            data = linha[:10]
            if data >= corte:
                linhas_recentes.append(linha.rstrip())
    return "\n".join(linhas_recentes)


def save_log(titulo):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now().strftime('%Y-%m-%d')}: {titulo}\n")


# ── CLAUDE ─────────────────────────────────────────────────────────────────────

def parse_json_response(text):
    text = text.strip()
    if "```" in text:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if match:
            text = match.group(1).strip()
    start = text.find("{")
    end   = text.rfind("}") + 1
    if start == -1 or end == 0:
        return {"status": "lista_vazia"}
    return json.loads(text[start:end])


def select_topic(candidates, historico, client):
    interesses_str  = ", ".join(INTERESSES)
    candidates_json = json.dumps(candidates, ensure_ascii=False)

    prompt = f"""Você é um sistema de seleção de tópicos de estudo para newsletter diária.

INTERESSES: {interesses_str}

HISTÓRICO — últimos {LOG_WINDOW_DAYS} dias (evitar repetição semântica):
{historico or "Nenhum ainda."}

CANDIDATOS:
{candidates_json}

Avalie cada candidato e selecione os melhores usando os critérios:
- C1 Atualidade (0-3): 3=últimos 7 dias | 2=últimos 30 dias com discussão ativa | 1=sem data | 0=sem ancoragem
- C2 Fit de interesse (0-3): 3=interesse exato | 2=subárea direta | 1=tangencia | 0=fora → descartar
- C3 Valor educacional (0-2): 2=ensina conceito/método aplicável | 1=breaking news ou fontes escassas | 0=só informa evento
- C4 Novidade (0-2): 2=inédito | 1=ângulo diferente | 0=repetição direta → descartar

Descartar automaticamente: C2=0 ou C4=0.
Desempate: C3 maior → C1 maior → C2 maior → mais fontes disponíveis.

Retorne APENAS JSON válido, sem nenhum texto adicional:
{{
  "status": "ok",
  "top1": {{"titulo": "...", "url": "...", "score": 0, "links": ["url1", "url2"]}},
  "top2": {{"titulo": "...", "url": "...", "links": ["url1"]}},
  "top3": {{"titulo": "...", "url": "...", "links": ["url1"]}}
}}

Se nenhum candidato for válido: {{"status": "lista_vazia"}}"""

    r = client.messages.create(model=MODEL, max_tokens=800,
                               messages=[{"role": "user", "content": prompt}])
    return parse_json_response(r.content[0].text)


def generate_email(topic, client):
    links = "\n".join(topic.get("links") or [topic["url"]])
    frase = random.choice(FRASES)

    prompt = f"""Escreva o conteúdo de um email de estudo diário em português brasileiro.

TÓPICO: {topic["titulo"]}
URL PRINCIPAL: {topic["url"]}
LINKS DISPONÍVEIS:
{links}

Retorne EXATAMENTE neste formato, sem texto antes ou depois:

ASSUNTO: [título direto, máximo 60 caracteres]

"{frase}"

[Parágrafo 1: o que é este tópico, por que é relevante agora e o conceito central — máximo 4 linhas]

[Parágrafo 2: como aplicar ou o que estudar a partir disto — máximo 3 linhas]

MATERIAIS:
- [URL mais relevante]: [descrição direta do que o leitor vai encontrar]
- [URL de aprofundamento]: [descrição direta do que o leitor vai encontrar]

Regras:
- Apenas 2 links — escolha os de maior valor para quem quer estudar o tema
- Direto, sem introduções, sem mencionar IA, sem emojis
- Os links devem ser URLs reais dos LINKS DISPONÍVEIS fornecidos acima"""

    r = client.messages.create(model=MODEL, max_tokens=1000,
                               messages=[{"role": "user", "content": prompt}])
    return r.content[0].text.strip()


def validate_email_content(content):
    """Retorna (subject, body) ou lança ValueError se o conteúdo for inválido."""
    lines        = content.split("\n")
    subject      = ""
    body_lines   = []
    reading_body = False

    for line in lines:
        if line.startswith("ASSUNTO:"):
            subject      = line.replace("ASSUNTO:", "").strip()
            reading_body = True
        elif reading_body:
            body_lines.append(line)

    body = "\n".join(body_lines).strip()

    if not subject:
        raise ValueError("Assunto ausente no conteúdo gerado.")
    if len(body) < 100:
        raise ValueError(f"Corpo do email muito curto ({len(body)} caracteres).")

    return subject, body


# ── EMAIL ──────────────────────────────────────────────────────────────────────

def send_email(subject, body):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = EMAIL_REMETENTE
    msg["To"]      = EMAIL_DESTINO
    msg.attach(MIMEText(body, "plain", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(EMAIL_REMETENTE, os.environ["GMAIL_APP_PASSWORD"])
        s.sendmail(EMAIL_REMETENTE, EMAIL_DESTINO, msg.as_string())


# ── MAIN ───────────────────────────────────────────────────────────────────────

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def try_topic(topic, client):
    """Tenta gerar e validar o email para um tópico. Retorna (subject, body) ou None."""
    try:
        content        = generate_email(topic, client)
        subject, body  = validate_email_content(content)
        return subject, body
    except Exception as e:
        log(f"Tópico '{topic['titulo']}' falhou: {e}")
        return None


def main():
    try:
        log("Buscando candidatos...")
        candidates = collect_candidates()
        log(f"{len(candidates)} candidatos únicos (limite: {MAX_CANDIDATES})")

        if not candidates:
            log("Nenhum candidato encontrado. Abortando.")
            return

        historico = load_log()
        client    = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

        log("Selecionando tópico...")
        selection = select_topic(candidates, historico, client)

        if selection.get("status") == "lista_vazia":
            log("Nenhum candidato válido após filtragem. Email não enviado.")
            return

        # tenta top1 → top2 → top3 em ordem
        resultado = None
        for chave in ["top1", "top2", "top3"]:
            topic = selection.get(chave)
            if not topic:
                continue
            log(f"Tentando {chave}: {topic['titulo']}")
            resultado = try_topic(topic, client)
            if resultado:
                break

        if not resultado:
            log("Todos os tópicos falharam na validação. Email não enviado.")
            return

        subject, body = resultado

        log(f"Enviando: {subject}")
        send_email(subject, body)

        # só loga após envio confirmado
        save_log(topic["titulo"])
        log("Concluído.")

    except Exception as e:
        log(f"Erro crítico: {e}")
        raise


if __name__ == "__main__":
    main()
