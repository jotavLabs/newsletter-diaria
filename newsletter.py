import os
import json
import smtplib
import requests
import feedparser
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import anthropic

from config import INTERESSES, EMAIL_DESTINO, EMAIL_REMETENTE

MODEL   = "claude-sonnet-4-5"
LOG     = "log.txt"


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
    candidates = []
    try:
        url  = (
            "http://export.arxiv.org/api/query"
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
    raw = fetch_hn() + fetch_arxiv() + fetch_google_news()
    seen, unique = set(), []
    for c in raw:
        if c["url"] not in seen:
            seen.add(c["url"])
            unique.append(c)
    return unique


# ── LOG ────────────────────────────────────────────────────────────────────────

def load_log():
    if not os.path.exists(LOG):
        return ""
    with open(LOG, "r", encoding="utf-8") as f:
        return f.read()


def save_log(titulo):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now().strftime('%Y-%m-%d')}: {titulo}\n")


# ── CLAUDE ─────────────────────────────────────────────────────────────────────

def select_topic(candidates, historico, client):
    interesses_str   = ", ".join(INTERESSES)
    candidates_json  = json.dumps(candidates, ensure_ascii=False)

    prompt = f"""Você é um sistema de seleção de tópicos de estudo para newsletter diária.

INTERESSES: {interesses_str}

HISTÓRICO (evitar repetição semântica):
{historico or "Nenhum ainda."}

CANDIDATOS:
{candidates_json}

Avalie cada candidato e selecione o melhor usando os critérios:
- C1 Atualidade (0-3): 3=últimos 7 dias | 2=últimos 30 dias com discussão ativa | 1=sem data | 0=sem ancoragem
- C2 Fit de interesse (0-3): 3=interesse exato | 2=subárea direta | 1=tangencia | 0=fora → descartar
- C3 Valor educacional (0-2): 2=ensina conceito/método aplicável | 1=breaking news ou fontes escassas | 0=só informa evento
- C4 Novidade (0-2): 2=inédito | 1=ângulo diferente | 0=repetição direta → descartar

Descartar automaticamente: C2=0 ou C4=0.
Desempate: C3 maior → C1 maior → C2 maior → mais fontes disponíveis.

Retorne APENAS JSON válido, sem nenhum texto adicional:
{{
  "status": "ok",
  "top1": {{
    "titulo": "título exato do candidato selecionado",
    "url": "url do candidato",
    "score": 0,
    "links": ["url_apoio_1", "url_apoio_2"]
  }},
  "fallback": [
    {{"url": "url_segundo_melhor"}},
    {{"url": "url_terceiro_melhor"}}
  ]
}}

Se nenhum candidato for válido: {{"status": "lista_vazia"}}"""

    r    = client.messages.create(model=MODEL, max_tokens=800,
                                  messages=[{"role": "user", "content": prompt}])
    text = r.content[0].text.strip()
    return json.loads(text[text.find("{"):text.rfind("}") + 1])


def generate_email(topic, client):
    links = "\n".join(topic.get("links") or [topic["url"]])

    prompt = f"""Escreva o conteúdo de um email de estudo diário em português brasileiro.

TÓPICO: {topic["titulo"]}
URL PRINCIPAL: {topic["url"]}
LINKS DISPONÍVEIS:
{links}

Retorne EXATAMENTE neste formato, sem texto antes ou depois:

ASSUNTO: [título direto, máximo 60 caracteres]

[Parágrafo 1: o que é este tópico e por que é relevante agora — 3 a 4 linhas]

[Parágrafo 2: como funciona ou qual o conceito central — 3 a 4 linhas]

[Parágrafo 3: como aplicar ou o que estudar a partir disto — 3 a 4 linhas]

MATERIAIS:
- [URL]: [descrição de uma linha]
- [URL]: [descrição de uma linha]
- [URL]: [descrição de uma linha]

Regras: direto, sem introduções, sem mencionar IA, sem emojis."""

    r = client.messages.create(model=MODEL, max_tokens=1200,
                               messages=[{"role": "user", "content": prompt}])
    return r.content[0].text.strip()


# ── EMAIL ──────────────────────────────────────────────────────────────────────

def send_email(content):
    lines         = content.split("\n")
    subject       = ""
    body_lines    = []
    reading_body  = False

    for line in lines:
        if line.startswith("ASSUNTO:"):
            subject      = line.replace("ASSUNTO:", "").strip()
            reading_body = True
        elif reading_body:
            body_lines.append(line)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = EMAIL_REMETENTE
    msg["To"]      = EMAIL_DESTINO
    msg.attach(MIMEText("\n".join(body_lines).strip(), "plain", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(EMAIL_REMETENTE, os.environ["GMAIL_APP_PASSWORD"])
        s.sendmail(EMAIL_REMETENTE, EMAIL_DESTINO, msg.as_string())

    return subject


# ── MAIN ───────────────────────────────────────────────────────────────────────

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def main():
    log("Buscando candidatos...")
    candidates = collect_candidates()
    log(f"{len(candidates)} candidatos únicos encontrados")

    historico = load_log()
    client    = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    log("Selecionando tópico...")
    selection = select_topic(candidates, historico, client)

    if selection.get("status") == "lista_vazia":
        log("Nenhum candidato válido. Email não enviado.")
        return

    topic = selection["top1"]
    log(f"Tópico: {topic['titulo']}")

    log("Gerando conteúdo...")
    content = generate_email(topic, client)

    log("Enviando email...")
    subject = send_email(content)

    save_log(topic["titulo"])
    log(f"Concluído: {subject}")


if __name__ == "__main__":
    main()
