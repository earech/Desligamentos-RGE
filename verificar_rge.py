import os, sys, base64, json
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright

DIAS_FRENTE = 5
URL = "https://spir.cpfl.com.br/Publico/ConsultaDesligamentoProgramado/Visualizar/4"

def formatar_data(dt):
    return dt.strftime("%d/%m/%Y")

def salvar(page, nome):
    page.screenshot(path=nome + ".png", full_page=True)
    with open(nome + ".html", "w", encoding="utf-8") as f:
        f.write(page.content())
    print("Salvo: " + nome)

def consultar(page):
    hoje = datetime.now()
    fim = hoje + timedelta(days=DIAS_FRENTE)

    print("Carregando pagina...")
    page.goto(URL, wait_until="networkidle", timeout=40000)
    page.wait_for_timeout(3000)
    salvar(page, "01_pagina_inicial")

    print("Submetendo via fetch direto...")
    resultado = page.evaluate("""
        async () => {
            var sel = document.getElementById('IdMunicipio');
            var idMunicipio = '';
            for (var i = 0; i < sel.options.length; i++) {
                if (sel.options[i].text.indexOf('Marcos') !== -1) {
                    idMunicipio = sel.options[i].value;
                    break;
                }
            }
            console.log('IdMunicipio encontrado: ' + idMunicipio);

            var params = new URLSearchParams();
            params.append('TipoConsulta', '2');
            params.append('from', '""" + formatar_data(hoje) + """');
            params.append('to', '""" + formatar_data(fim) + """');
            params.append('IdMunicipio', idMunicipio);
            params.append('Bairro', 'Industrial');
            params.append('Rua', '');

            var resp = await fetch('/Publico/ConsultaDesligamentoProgramado/Pesquisar', {
                method: 'POST',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: params.toString()
            });
            return await resp.text();
        }
    """)

    print("=== RESPOSTA ===")
    print(str(resultado)[:3000])
    print("=== FIM ===")

    # Tenta parsear como JSON
    desligamentos = []
    try:
        dados = json.loads(resultado)
        if isinstance(dados, list):
            desligamentos = dados
        elif isinstance(dados, dict):
            for chave in dados:
                if isinstance(dados[chave], list):
                    desligamentos = dados[chave]
                    break
    except Exception:
        # Nao e JSON, verifica se texto indica sem resultado
        if "Nenhum desligamento" in str(resultado):
            return []

    return desligamentos

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(locale="pt-BR").new_page()
        try:
            desligamentos = consultar(page)
        except Exception as e:
            page.screenshot(path="erro.png", full_page=True)
            print("Erro: " + str(e))
            browser.close()
            sys.exit(1)
        browser.close()

    hoje = datetime.now()
    fim = hoje + timedelta(days=DIAS_FRENTE)
    periodo = formatar_data(hoje) + " ate " + formatar_data(fim)

    if not desligamentos:
        corpo = "Nenhum desligamento em Sao Marcos - Industrial. Periodo: " + periodo
        tem_alerta = False
    else:
        linhas = ["ALERTA: " + str(len(desligamentos)) + " desligamento(s) em Sao Marcos - Industrial"]
        linhas.append("Periodo: " + periodo)
        for i, d in enumerate(desligamentos, 1):
            linhas.append("--- Desligamento " + str(i) + " ---")
            if isinstance(d, dict):
                for k, v in d.items():
                    linhas.append("  " + str(k) + ": " + str(v))
            else:
                linhas.append("  " + str(d))
        linhas.append("Veja em: " + URL)
        corpo = "\n".join(linhas)
        tem_alerta = True

    print(corpo)

    gh = os.environ.get("GITHUB_OUTPUT", "")
    if gh:
        b64 = base64.b64encode(corpo.encode("utf-8")).decode()
        with open(gh, "a") as f:
            f.write("status=" + ("alerta" if tem_alerta else "ok") + "\n")
            f.write("tem_desligamento=" + ("true" if tem_alerta else "false") + "\n")
            f.write("corpo_b64=" + b64 + "\n")

    sys.exit(0)

if __name__ == "__main__":
    main()
