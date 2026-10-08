#!/usr/bin/env python3
"""Importa somente textos oficiais integrais, com validação antes da indexação."""
from pathlib import Path
import re
import sys
from html import escape
from urllib.parse import urlparse
from datetime import datetime, timezone
import requests
from bs4 import BeautifulSoup

NORMAS = [
 ("Lei Complementar 101/2000 — Responsabilidade Fiscal","leis-complementares/lc-101-2000.html","https://www.planalto.gov.br/ccivil_03/leis/lcp/lcp101.htm",65),
 ("Lei 4.320/1964 — Normas Gerais de Direito Financeiro","leis/lei-4320-1964.html","https://www.planalto.gov.br/ccivil_03/leis/l4320.htm",100),
 ("Decreto 9.094/2017 — Simplificação de Serviços Públicos","decretos/decreto-9094-2017.html","https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2017/decreto/d9094.htm",20),
 ("Decreto 9.830/2019 — Regulamentação da LINDB","decretos/decreto-9830-2019.html","https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2019/decreto/d9830.htm",25),
 ("Lei 13.869/2019 — Abuso de Autoridade","leis/lei-13869-2019.html","https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2019/lei/l13869.htm",35),
 ("Lei 12.232/2010 — Serviços de Publicidade","leis/lei-12232-2010.html","https://www.planalto.gov.br/ccivil_03/_ato2007-2010/2010/lei/l12232.htm",20),

]
session=requests.Session()
session.headers.update({"User-Agent":"Mozilla/5.0 (compatible; NormativosImport/1.0)"})
changes=[]
for titulo,caminho,url,min_artigos in NORMAS:
    dest=Path(caminho)
    if dest.exists():
        print("EXISTENTE",caminho)
        continue
    try:
        r=session.get(url,timeout=50)
        r.raise_for_status()
        if "text/html" not in r.headers.get("content-type","").lower():
            raise ValueError("Fonte não disponibiliza HTML integral")
        r.encoding=r.apparent_encoding or r.encoding
        soup=BeautifulSoup(r.text,"html.parser")
        if not soup.html:
            raise ValueError("Ausente estrutura HTML")
        for bad in soup(["script","style","iframe"]): bad.decompose()
        text=soup.get_text(" ",strip=True)
        matches=re.findall(r"\bArt\.?\s*\d+[º°o]?(?:-?[A-Z])?\b",text,re.I)
        if len(matches)<min_artigos or len(text)<4000:
            raise ValueError(f"Texto insuficiente: {len(matches)} artigos, {len(text)} caracteres")
        title=soup.find("title")
        if title is None:
            title=soup.new_tag("title")
            (soup.head or soup.html).insert(0,title)
        title.string=titulo
        meta=soup.new_tag("meta",charset="utf-8")
        if soup.head: soup.head.insert(0,meta)
        unique=set()
        for tag in soup.find_all(["p","div","span","h1","h2","h3","h4"]):
            if tag.find(["p","div","span","h1","h2","h3","h4"]):
                continue
            m=re.match(r"^\s*Art\.?\s*(\d+[º°o]?(?:-?[A-Z])?)\s*[.\-–]?",tag.get_text(" ",strip=True),re.I)
            if m:
                normalized=re.sub(r"[^a-z0-9]","",m.group(1).lower())
                anchor="art-"+normalized
                if anchor not in unique:
                    tag["id"]=anchor
                    unique.add(anchor)
        if len(unique)<max(5,min_artigos//4):
            raise ValueError(f"Falha de ancoragem: {len(unique)} âncoras")
        provenance=soup.new_tag("meta")
        provenance.attrs={"name":"fonte-oficial","content":url}
        if soup.head: soup.head.append(provenance)
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(str(soup),encoding="utf-8")
        changes.append((titulo,caminho,url))
        print("CRIADO",caminho,len(unique),"âncoras",len(text),"caracteres")
    except Exception as e:
        print("NÃO INCLUÍDO",caminho,type(e).__name__,str(e))
if changes:
    idx=Path("index.html")
    content=idx.read_text(encoding="utf-8")
    grouped={"tce-go":[],"goias":[],"federais":[]}
    for titulo,caminho,url in changes:
        if caminho.startswith("tce-go/"):grouped["tce-go"].append((titulo,caminho,url))
        elif caminho.startswith("goias/"):grouped["goias"].append((titulo,caminho,url))
        else:grouped["federais"].append((titulo,caminho,url))
    section='<section id="normas-programa-tce-go"><h2>Normativos — Programa TCE-GO</h2>'
    for key,label in [("tce-go","TCE-GO"),("goias","Estado de Goiás"),("federais","Normas federais")]:
        if grouped[key]:
            section+='<h3>'+label+'</h3><ul>'
            for titulo,caminho,url in grouped[key]:
                section+='<li><a href="'+escape(caminho,quote=True)+'">'+escape(titulo)+'</a><small>Fonte oficial: <a href="'+escape(url,quote=True)+'">'+escape(url)+'</a></small></li>'
            section+='</ul>'
    section+='</section>'
    if 'id="normas-programa-tce-go"' in content:
        raise RuntimeError("Seção do programa já existe; abortando para não duplicar índice")
    if "</body>" not in content: raise RuntimeError("index.html inválido: falta </body>")
    content=content.replace('</body>',section+'</body>',1)
    idx.write_text(content,encoding="utf-8")
print("TOTAL CRIADOS",len(changes),"DE",len(NORMAS))
if not changes: print("Sem novos arquivos; execução idempotente")
