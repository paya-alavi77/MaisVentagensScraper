
# README (Português) — Para Iniciantes

## Relatório Downloader (Extensão do Chrome)

Esta extensão ajuda você a **atualizar automaticamente** uma tabela no banco (Supabase) com os atendimentos do site **sistemas.infornet.com.br**, usando o seu login já feito no navegador.

Você só precisa:
- Instalar a extensão no Chrome
- Estar logado no site
- Clicar em **Atualizar**

---

## 1) Como instalar no Google Chrome

1. Baixe este projeto (pasta com os arquivos [manifest.json](cci:7://file:///Users/felipequadros/MaisVentagensScraper/manifest.json:0:0-0:0), [popup.html](cci:7://file:///Users/felipequadros/MaisVentagensScraper/popup.html:0:0-0:0), [popup.js](cci:7://file:///Users/felipequadros/MaisVentagensScraper/popup.js:0:0-0:0))
   - Se você baixou do GitHub: clique em **Code → Download ZIP**
   - Depois **descompacte** (extraia) a pasta

2. Abra o Chrome e vá para:
   - `chrome://extensions/`

3. Ative **Modo do desenvolvedor**
   - Normalmente fica no canto superior direito da página

4. Clique em **Carregar sem compactação** (ou **Load unpacked**)

5. Selecione a pasta do projeto (a pasta que tem [manifest.json](cci:7://file:///Users/felipequadros/MaisVentagensScraper/manifest.json:0:0-0:0))

Pronto — a extensão vai aparecer na lista.

---

## 2) Como usar (passo a passo)

1. Abra o site e faça login:
   - `https://sistemas.infornet.com.br`

2. Depois de estar logado, clique no ícone da extensão no Chrome
   - Se não aparecer, clique no ícone de “peça de quebra-cabeça” (Extensões) e fixe a extensão para ela aparecer sempre

3. A extensão vai mostrar duas datas:
   - **Data Início**
   - **Data Final**

Geralmente ela já preenche automaticamente:
- **Data Início**: última data que já está salva no banco (mais 1 dia)
- **Data Final**: hoje

4. Clique no botão **Atualizar**

5. Aguarde a mensagem de status:
- Se der certo: aparece uma mensagem de sucesso
- Se der erro: aparece uma mensagem explicando (ex.: sessão expirada)

---

## 3) Se der erro (o que fazer)

- **“Sessão expirada” / “faça login novamente”**
  - Volte no site, faça login de novo e tente novamente

- **“Acesse sistemas.infornet.com.br primeiro”**
  - Abra o site e deixe ele aberto em uma aba, logado

---

# README (English) — Beginner Friendly

## Relatório Downloader (Chrome Extension)

This extension helps you **automatically update** a database table (Supabase) with “atendimentos” data from **sistemas.infornet.com.br**, using your current login session in the browser.

All you do is:
- Install it in Chrome
- Be logged in on the website
- Click **Atualizar**

---

## 1) How to install in Google Chrome

1. Download this project folder (it contains [manifest.json](cci:7://file:///Users/felipequadros/MaisVentagensScraper/manifest.json:0:0-0:0), [popup.html](cci:7://file:///Users/felipequadros/MaisVentagensScraper/popup.html:0:0-0:0), [popup.js](cci:7://file:///Users/felipequadros/MaisVentagensScraper/popup.js:0:0-0:0))
   - If you downloaded from GitHub: click **Code → Download ZIP**
   - Then **extract/unzip** the folder

2. Open Chrome and go to:
   - `chrome://extensions/`

3. Enable **Developer mode**
   - Usually on the top-right corner

4. Click **Load unpacked**

5. Select the project folder (the one that contains [manifest.json](cci:7://file:///Users/felipequadros/MaisVentagensScraper/manifest.json:0:0-0:0))

Done — the extension should now appear in the list.

---

## 2) How to use (step by step)

1. Open the website and log in:
   - `https://sistemas.infornet.com.br`

2. While you are logged in, click the extension icon in Chrome
   - If you don’t see it, click the puzzle icon (Extensions) and pin the extension

3. You will see two dates:
   - **Data Início** (Start Date)
   - **Data Final** (End Date)

Usually it auto-fills:
- **Start Date**: the last date already saved in the database (plus 1 day)
- **End Date**: today

4. Click **Atualizar**

5. Wait for the status message:
- Success message if everything worked
- Error message if something went wrong (like an expired session)

---

## 3) If you get an error

- **“Sessão expirada” / “login again”**
  - Go back to the site, log in again, and try once more

- **“Acesse sistemas.infornet.com.br primeiro”**
  - Open the website in a tab and make sure you are logged in


