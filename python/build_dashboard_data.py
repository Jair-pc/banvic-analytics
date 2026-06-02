# -*- coding: utf-8 -*-
"""
BanVic Analytics — ETL Gold (Python)
=====================================
Le os CSVs brutos em data/raw, executa as transformacoes em Pandas
(equivalentes as queries em sql/03..06) e gera o JSON compacto consumido
pelo Dashboard web V2.

Entrada:  data/raw/*.csv
Saida:    output/banvic_v2_report.json

Rodar a partir da raiz do repo:
    python python/build_dashboard_data.py
"""
import pandas as pd, numpy as np, json, io, os, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
BASE = ROOT / "data" / "raw"
OUTDIR = ROOT / "output"
OUTDIR.mkdir(exist_ok=True)
OUTFILE = OUTDIR / "banvic_v2_report.json"

def rc(n):
    p = str(BASE / n)
    for e in ("utf-8-sig","utf-8","latin-1"):
        try: return pd.read_csv(p, encoding=e)
        except UnicodeDecodeError: continue
    return pd.read_csv(p, encoding="latin-1")

tx=rc("transacoes.csv"); ct=rc("contas.csv"); cli=rc("clientes.csv"); ag=rc("agencias.csv")
col=rc("colaboradores.csv"); ca=rc("colaborador_agencia.csv"); prop=rc("propostas_credito.csv")
ipca=rc("ipca.csv")
MES={'JAN':1,'FEV':2,'MAR':3,'ABR':4,'MAI':5,'JUN':6,'JUL':7,'AGO':8,'SET':9,'OUT':10,'NOV':11,'DEZ':12}
INV={v:k for k,v in MES.items()}; ipca['mn']=ipca['mes'].map(MES)

# limpa nome agencia ("Agência Matriz" -> "Matriz")
ag['short']=ag['nome'].str.replace('Agência ','',regex=False).str.replace('Agencia ','',regex=False).str.strip()
AGS=ag.sort_values('cod_agencia')[['cod_agencia','short','uf','tipo_agencia']].to_dict('records')
AGIDX={r['cod_agencia']:i for i,r in enumerate(AGS)}   # cod_agencia -> 0..9

# colaboradores por agencia
colpa=ca.groupby('cod_agencia').size()

# clientes: faixa etaria + estado (via conta->agencia)
cli['nasc']=pd.to_datetime(cli['data_nascimento'],errors='coerce')
ref=pd.Timestamp('2023-01-01'); cli['idade']=((ref-cli['nasc']).dt.days/365.25)
FAIXAS=['Jovem (<25)','Adulto (25-59)','Idoso (60+)']
def fidx(a):
    if pd.isna(a): return 3
    if a<25: return 0
    if a<60: return 1
    return 2
cli['fidx']=cli['idade'].apply(fidx)
cli['inc']=pd.to_datetime(cli['data_inclusao'],utc=True,errors='coerce'); cli['incY']=cli['inc'].dt.year
# estado do cliente = estado da agencia da sua conta principal
cc=ct[['cod_cliente','cod_agencia','saldo_total','tipo_conta']].merge(ag[['cod_agencia','uf','short']],on='cod_agencia',how='left')
cli=cli.merge(cc.drop_duplicates('cod_cliente')[['cod_cliente','cod_agencia','uf','saldo_total']],on='cod_cliente',how='left')

ESTADOS=['SP','RJ','RS','SC','PE']; EIDX={e:i for i,e in enumerate(ESTADOS)}
TIPOS=list(tx['nome_transacao'].value_counts().index)  # ordenado por freq
TIDX={t:i for i,t in enumerate(TIPOS)}

# ---- join transacoes -> conta(agencia, cliente) -> cliente(faixa) ----
txj=tx.merge(ct[['num_conta','cod_agencia','cod_cliente']],on='num_conta',how='left')
txj=txj.merge(cli[['cod_cliente','fidx']],on='cod_cliente',how='left')
txj['fidx']=txj['fidx'].fillna(3).astype(int)
txj['d']=pd.to_datetime(txj['data_transacao'],format='mixed',utc=True,errors='coerce')
txj['ano']=txj['d'].dt.year.fillna(0).astype(int); txj['mes']=txj['d'].dt.month.fillna(0).astype(int)
txj['ai']=txj['cod_agencia'].map(AGIDX)
txj['ti']=txj['nome_transacao'].map(TIDX)
txj['av']=txj['valor_transacao'].abs()

# FACT 1: evolucao  (ano,mes,ai,fidx) -> [cnt, volR]
f1=txj.groupby(['ano','mes','ai','fidx'],dropna=False).agg(cnt=('av','size'),vol=('av','sum')).reset_index()
f1=f1[f1['ano']>0]
txEvo=[[int(r.ano),int(r.mes),int(r.ai),int(r.fidx),int(r.cnt),int(round(r.vol))] for r in f1.itertuples()]

# FACT 2: tipo  (ano,ai,fidx,ti) -> [cnt, volR]   (filtravel por ano+agencia+faixa)
f2=txj[txj['ano']>0].groupby(['ano','ai','fidx','ti']).agg(cnt=('av','size'),vol=('av','sum')).reset_index()
txType=[[int(r.ano),int(r.ai),int(r.fidx),int(r.ti),int(r.cnt),int(round(r.vol))] for r in f2.itertuples()]

# FACT 3: clientes (ai,fidx,eidx,incY) -> cnt   + saldo
cli['ai']=cli['cod_agencia'].map(AGIDX); cli['ei']=cli['uf'].map(EIDX)
f3=cli.dropna(subset=['ai']).groupby(['ai','fidx','ei','incY']).agg(cnt=('cod_cliente','size'),saldo=('saldo_total','sum')).reset_index()
cliFact=[[int(r.ai),int(r.fidx),int(r.ei),int(r.incY) if not pd.isna(r.incY) else 0,int(r.cnt),int(round(r.saldo)) if not pd.isna(r.saldo) else 0] for r in f3.itertuples()]

# FACT 4: propostas  (ano,ai,fidx,statusIdx) -> [cnt,sumValor,sumJuros,sumParc,sumFin,sumEntr]
prop['pd']=pd.to_datetime(prop['data_entrada_proposta'],utc=True,errors='coerce'); prop['ano']=prop['pd'].dt.year.fillna(0).astype(int)
prop=prop.merge(cli[['cod_cliente','fidx','ai']],on='cod_cliente',how='left')
# agencia da proposta: via cliente (ai). fallback: colaborador->agencia
colag=ca.set_index('cod_colaborador')['cod_agencia'].to_dict()
prop['ai_col']=prop['cod_colaborador'].map(lambda c: AGIDX.get(colag.get(c)))
prop['ai']=prop['ai'].fillna(prop['ai_col'])
prop['fidx']=prop['fidx'].fillna(3).astype(int)
STATUS=['Enviada','Aprovada','Validacao documentos','Em analise']
def sidx(s):
    s=str(s).lower()
    if 'aprov' in s: return 1
    if 'valid' in s: return 2
    if 'an' in s and 'lise' in s.replace('á','a'): return 3
    if 'envi' in s: return 0
    return 0
prop['si']=prop['status_proposta'].apply(sidx)
prop=prop.dropna(subset=['ai'])
f4=prop.groupby(['ano','ai','fidx','si']).agg(cnt=('cod_proposta','size'),val=('valor_proposta','sum'),
     jur=('taxa_juros_mensal','sum'),parc=('quantidade_parcelas','sum'),
     fin=('valor_financiamento','sum'),ent=('valor_entrada','sum')).reset_index()
propFact=[[int(r.ano),int(r.ai),int(r.fidx),int(r.si),int(r.cnt),int(round(r.val)),
           round(float(r.jur),4),int(round(r.parc)),int(round(r.fin)),int(round(r.ent))] for r in f4.itertuples()]

# distribuicao de juros (faixas) e parcelas — para histogramas (por ano/ai/fidx seria grande; faz global + guarda raw leve)
prop['jur_pct']=prop['taxa_juros_mensal']*100
jbins=[0.8,1.0,1.2,1.4,1.6,1.8,2.0,2.2,2.5]
jl=['0,8-1,0','1,0-1,2','1,2-1,4','1,4-1,6','1,6-1,8','1,8-2,0','2,0-2,2','2,2-2,5']
prop['jb']=pd.cut(prop['jur_pct'],bins=jbins,labels=jl,include_lowest=True)
# guardamos proposta-nivel MUITO leve p/ filtrar juros/parcelas no JS: (ano,ai,fidx,jbIdx,parc)
JL=jl
prop['jbi']=prop['jb'].map({l:i for i,l in enumerate(jl)})
propRaw=[[int(r.ano),int(r.ai),int(r.fidx),int(r.jbi) if not pd.isna(r.jbi) else 0,int(r.quantidade_parcelas)]
         for r in prop.itertuples()]

# IPCA mensal (para combo) — serie por ano-mes: [ano, mn, no_mes, 12_meses]
ipca['m12']=pd.to_numeric(ipca['12_meses'],errors='coerce')
ipS=ipca[ipca['ano'].between(2018,2022)].sort_values(['ano','mn'])
ipcaSer=[[int(r.ano),int(r.mn),round(float(r.no_mes),2),round(float(r.m12),2) if not pd.isna(r.m12) else None] for r in ipS.itertuples()]

# FACT saques: (ano,mes,ai,fidx) -> volSaque  (para IPCA x saques)
sq=txj[txj['nome_transacao'].str.lower().str.contains('saque',na=False)]
fsq=sq[sq['ano']>0].groupby(['ano','mes','ai','fidx']).agg(vol=('av','sum')).reset_index()
saqueFact=[[int(r.ano),int(r.mes),int(r.ai),int(r.fidx),int(round(r.vol))] for r in fsq.itertuples()]

# dims/estaticos
dims=dict(
  agencias=[{"i":i,"nome":r['short'],"uf":r['uf'],"tipo":r['tipo_agencia'],
             "colab":int(colpa.get(r['cod_agencia'],0))} for i,r in enumerate(AGS)],
  faixas=FAIXAS, estados=ESTADOS, tipos=TIPOS, jurosBins=JL,
  totals=dict(clientes=998, contas=int(len(ct)), colaboradores=int(len(col)),
              agencias=int(len(ag)), saldoTotal=int(round(ct['saldo_total'].sum())))
)
# === DIM_DATES: analises temporais (exclui dump artificial de fim de 2022) ===
from scipy import stats
txd=txj.dropna(subset=['d']).copy()
txd['date']=txd['d'].dt.normalize()
dly=txd.groupby('date').agg(cnt=('av','size'),vol=('av','sum')).reset_index()
DUMP_THR=200
dump_days=dly[dly['cnt']>DUMP_THR]
clean=dly[dly['cnt']<=DUMP_THR].copy()
clean['ano']=clean['date'].dt.year; clean['tri']=clean['date'].dt.quarter
clean['mes']=clean['date'].dt.month; clean['dow']=clean['date'].dt.dayofweek
RMES={1,2,3,4,9,10,11,12}
clean['temR']=clean['mes'].isin(RMES); clean['par']=clean['mes']%2==0
def tblock(df):
    tri=[{"q":int(q),"c":round(float(g['cnt'].mean()),2),"v":int(round(g['vol'].mean()))} for q,g in df.groupby('tri')]
    wd=[{"d":int(d),"c":round(float(g['cnt'].mean()),2),"v":int(round(g['vol'].mean()))} for d,g in df.groupby('dow')]
    cR,sR=df[df.temR]['cnt'],df[~df.temR]['cnt']
    pr=float(stats.ttest_ind(cR,sR,equal_var=False).pvalue) if len(cR)>1 and len(sR)>1 else 1.0
    pa,im=df[df.par]['vol'],df[~df.par]['vol']
    pp=float(stats.ttest_ind(pa,im,equal_var=False).pvalue) if len(pa)>1 and len(im)>1 else 1.0
    return dict(tri=tri,wd=wd,
        rmonths=dict(comR=round(float(cR.mean()),2),semR=round(float(sR.mean()),2),p=round(pr,4)),
        parimpar=dict(par=int(round(pa.mean())),impar=int(round(im.mean())),p=round(pp,4)))
tempoByYear={"all":tblock(clean)}
for y in (2020,2021,2022):
    sub=clean[clean['ano']==y]
    tempoByYear[str(y)]=tblock(sub) if len(sub)>3 else None
tempo=dict(byYear=tempoByYear,dumpDays=int(len(dump_days)),
           txClean=int(clean['cnt'].sum()),txTotal=int(dly['cnt'].sum()),
           dumpList=[str(d.date()) for d in dump_days['date']])

out=dict(dims=dims, txEvo=txEvo, txType=txType, cliFact=cliFact,
         propFact=propFact, propRaw=propRaw, ipcaSer=ipcaSer, saqueFact=saqueFact, tempo=tempo)
io.open(str(OUTFILE),"w",encoding="utf-8").write(json.dumps(out,ensure_ascii=False,separators=(',',':')))
sz=os.path.getsize(str(OUTFILE))
print("OK  saida=%s  (%.0f KB)" % (OUTFILE, sz/1024))
print("txEvo rows:",len(txEvo)," txType:",len(txType)," cliFact:",len(cliFact)," propFact:",len(propFact)," propRaw:",len(propRaw))
print("tipos:",TIPOS[:6],"...")
print("saldoTotal R$:",dims['totals']['saldoTotal'])
print("agencias:",[a['nome'] for a in dims['agencias']])
