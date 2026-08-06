<div align="center">

# 📰 Newsletter Diária

**Uma newsletter de estudo que se monta sozinha, todo dia de manhã.**

Coleta conteúdo de várias fontes, usa a **API da Claude** para escolher o melhor tópico do dia (sem repetir o que você já recebeu) e envia um e-mail pronto para estudar — 100% automatizado via **GitHub Actions**.

![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![Claude API](https://img.shields.io/badge/Claude_API-Anthropic-D97757?logo=anthropic&logoColor=white)
![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-cron%20diário-2088FF?logo=githubactions&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-blue)

</div>

---

## 💡 Sobre

Eu queria estudar um pouco todo dia, mas perdia tempo garimpando o que valia a pena ler — e acabava caindo sempre nos mesmos assuntos. Então automatizei isso.

Todo dia às **8h (horário de Brasília)** um robô vasculha a internet por temas dos meus interesses, pede para a **Claude** ranquear os candidatos e escrever um e-mail curto e direto sobre o melhor deles, e me entrega na caixa de entrada. Sem app, sem servidor, sem custo fixo — roda inteiro no GitHub Actions.

## ⚙️ Como funciona

```
Fontes  ──►  Coleta  ──►  Curadoria (Claude)  ──►  Redação (Claude)  ──►  E-mail
  HN          dedup         pontua e escolhe        gera o conteúdo       Gmail SMTP
  arXiv       (top 30)      evitando repetição        em PT-BR
  Google News               (log de 120 dias)
```

1. **Coleta** — busca candidatos em três fontes, por interesse:
   - **Hacker News** (API Algolia)
   - **arXiv** (só quando há interesses científicos — biologia, física, matemática, filosofia…)
   - **Google News** (RSS, pt-BR)

   Os resultados são deduplicados por URL e cortados nos 30 melhores candidatos.

2. **Curadoria com a Claude** — os candidatos vão para o modelo com uma **rubrica de pontuação** explícita (atualidade, fit de interesse, valor educacional e novidade). O modelo descarta o que está fora do tema ou repetido e devolve um top 3 em **JSON estruturado**.

3. **Memória anti-repetição** — um `log.txt` versionado guarda o que já foi enviado. Os últimos **120 dias** entram no prompt para a Claude evitar repetir assunto — e o GitHub Actions faz commit do log de volta no fim de cada execução.

4. **Redação** — a Claude escreve o e-mail final em PT-BR: assunto curto, uma frase filosófica de abertura, dois parágrafos (o conceito + como aplicar) e uma lista de materiais para aprofundar.

5. **Envio** — o e-mail sai por **Gmail SMTP** para a lista de destinatários.

## 🧱 Stack

| Camada | Tecnologia |
|--------|-----------|
| Linguagem | Python 3.11 |
| IA / curadoria | Anthropic **Claude** (`claude-sonnet-4-5`) |
| Coleta | `requests` (Hacker News) · `feedparser` (arXiv, Google News RSS) |
| E-mail | `smtplib` + `email` (Gmail SMTP) |
| Orquestração | GitHub Actions (cron diário + `workflow_dispatch`) |

## ▶️ Como rodar

```bash
git clone https://github.com/jotavLabs/newsletter-diaria
cd newsletter-diaria
pip install -r requirements.txt
python newsletter.py
```

### Configuração

1. **Edite `config.py`** com seus interesses e os e-mails de origem/destino:

   ```python
   INTERESSES      = ["filosofia antiga", "neurociência cognitiva", ...]
   EMAIL_DESTINOS  = ["voce@exemplo.com"]
   EMAIL_REMETENTE = "seu-gmail@gmail.com"
   ```

2. **Defina os secrets** (variáveis de ambiente / GitHub Secrets):

   | Secret | Para que serve |
   |--------|----------------|
   | `ANTHROPIC_API_KEY` | Acesso à API da Claude |
   | `GMAIL_APP_PASSWORD` | [Senha de app](https://support.google.com/accounts/answer/185833) do Gmail remetente |

### Execução automática

O workflow [`.github/workflows/daily.yml`](.github/workflows/daily.yml) roda todo dia às **11h UTC (8h Brasília)** e também pode ser disparado manualmente em **Actions → Run workflow**. Basta cadastrar os dois secrets acima no repositório.

## 🗺️ Estrutura

```
newsletter-diaria/
├── newsletter.py            # pipeline: coleta → curadoria → redação → envio
├── config.py                # interesses e e-mails (você edita)
├── requirements.txt         # anthropic · feedparser · requests
├── log.txt                  # histórico de tópicos enviados (anti-repetição)
├── public/
│   └── index.html           # mini-aula em slides (site estático)
├── vercel.json              # publica public/ como site estático
└── .github/workflows/
    └── daily.yml            # cron diário no GitHub Actions
```

## 🎓 Mini-aula em slides

`public/index.html` é um deck autocontido — um único arquivo, sem dependências, sem build — com a mini-aula **"Investir sem se dar mal"**: 44 slides em 6 módulos, cada um com resumo, exemplos do dia a dia, dados de pesquisa e um recurso gratuito.

| Tecla | Ação |
|-------|------|
| `→` `␣` | Avançar · `←` voltar |
| `O` | Índice de todos os slides |
| `N` | Notas do apresentador |
| `T` | Cronômetro da aula |
| `F` | Tela cheia · `?` atalhos |

`Ctrl/⌘ + P` imprime como apostila: um slide por página, com as notas junto. O deck acompanha o tema claro/escuro do sistema e funciona no celular.

### Publicando

Abrir o arquivo direto no navegador já funciona. Para colocar no ar, o `vercel.json` já aponta a Vercel para `public/`:

```bash
npx vercel --prod        # a partir da raiz do repositório
```

Ou importe o repositório em [vercel.com/new](https://vercel.com/new) — a configuração é lida do `vercel.json`, sem nada a preencher.

## 📄 Licença

MIT © João Bento
