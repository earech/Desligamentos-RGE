#!/usr/bin/env python3
"""
Monitor de Desligamentos Programados - RGE / CPFL
Usa Playwright para simular o navegador e consultar o formulário real do SPIR.
"""

import os
import sys
import base64
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

MUNICIPIO = "São Marcos"
DIAS_FRENTE = 5
URL = "https://spir.cpfl.com.br/Publico/ConsultaDesligamentoProgramado/Visualizar/4"


def formatar_data(dt: datetime) -> str:
    return dt.strftime("%d/%m/%Y")


def consultar(page) -> list:
    hoje = datetime.now()
    fim = hoje + timedelta(days=DIAS_FRENTE)

    print(f"Acessando {URL} ...")
    page.goto(URL, wait_until="networkidle", timeout=30000)

    page.locator("label", has_text="Por Localização").click()
    page.wait_for_timeout(500)

    campo_inicio = page.locator("input[name='DataInicio'], input#DataInicio").first
    campo_inicio.fill(formatar_data(hoje))

    campo_fim = page.locator("input[name='DataFim'], input#DataFim").first
    campo_fim.fill(formatar_data(fim))

    select = page.locator("select[name='Municipio'], select#Municipio").first
    select.select_option(label=MUNICIPIO)
    page.wait_for_timeout(300)

    print(f"Pesquisando {MUNICIPIO} de {formatar_data(hoje)} até {formatar_data(fim)} ...")

    page.locator("button:has-text('Pesquisar'), input[value='Pesquisar']").first.click()

    page.wait_for_selector(
        "text=Nenhum desligamento, table, .resultado, #resultado, .desligamentos",
        timeout=20000
    )

    if page.locator("text=Nenhum desligamento programado").count() > 0:
        return []

    desligamentos = []
    linhas = page.locator("table tr").all()
    cabecalhos = []

    for i, linha in enumerate(linhas):
        celulas = [c.inner_text().strip() for c in linha.locator("td, th").all()]
        if not celulas:
            continue
        if i == 0:
            cabecalhos = celulas
        else:
            item = dict(zip(cabecalhos, celulas)) if cabecalhos else {"info": " | ".join(celulas)}
            desligamentos.append(item)

    if not desligamentos:
        texto = page.locator("main, body").first.inner_text().strip()
        if texto:
            desligamentos.append({"texto": texto[:500]})

    return desligamentos


def montar_mensagem(desligamentos: list) -> tuple:
    hoje = datetime.now()
    fim = hoje + timedelta(days=DIAS_FRENTE)
    periodo = f"{formatar_data(hoje)} até {formatar_data(fim)}"

    if not desligamentos:
        corpo = (
            f"Nenhum desligamento programado em {MUNICIPIO}.\n\n"
            f"Periodo verificado: {periodo}\n\n"
            "---\nMonitor automatico RGE via GitHub Actions"
        )
        return False, corpo

    linhas = [
        f"ALERTA: {len(desligamentos)} desligamento(s) encontrado(s) em {MUNICIPIO}!",
        f"Periodo verificado: {periodo}",
        "",
    ]
    for i, d in enumerate(desligamentos, 1):
        linhas.append(f"--- Desligamento {i} ---")
        for k, v in d.items():
            linhas.append(f"  {k}: {v}")
        linhas.append("")

    linhas += [
        "Consulte detalhes em:",
        URL,
        "",
        "---",
        "Monitor automatico RGE via GitHub Actions",
    ]
    return True, "\n".join(linhas)


def exportar_github_output(tem_alerta: bool, corpo: str):
    gh_output = os.environ.get("GITHUB_OUTPUT", "")
    if not gh_output:
        return
    corpo_b64 = base64.b64encode(corpo.encode("utf-8")).decode()
    with open(gh_output, "a") as f:
        f.write(f"status={'alerta' if tem_alerta else 'ok'}\n")
        f.write(f"tem_desligamento={'true' if tem_alerta else 'false'}\n")
        f.write(f"corpo_b64={corpo_b64}\n")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            locale="pt-BR",
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
        )
        page = context.new_page()

        try:
            desligamentos = consultar(page)
        except PlaywrightTimeout as e:
            print(f"Timeout: {e}")
            browser.close()
            sys.exit(1)
        except Exception as e:
            print(f"Erro: {e}")
            browser.close()
            sys.exit(1)

        browser.close()

    tem_alerta, corpo = montar_mensagem(desligamentos)
    print(corpo)
    exportar_github_output(te
