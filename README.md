# Viamão 2026 — dashboard

## Deploy na Vercel

Este é um dashboard estático. A configuração em `vercel.json` abre `dashboard/index.html` na raiz.

Antes do deploy, gere os artefatos reais em `data/processed/`:

```bash
python -m pip install -r requirements.txt
python src/data_processing.py
python src/similarity_analysis.py
python src/map_builder.py
```

Para validar localmente:

```bash
python -m http.server 8000
```

Abra `http://localhost:8000/dashboard/`.

### Observações

- Os arquivos originais permanecem preservados na raiz do repositório.
- O mapa representa locais de votação; não representa a residência dos eleitores.
- A análise de similaridade é descritiva e tem a seção como unidade de análise.
- O XLSX possui registros finais com múltiplas seções; eles devem permanecer sinalizados como anomalia.

Depois de confirmar que os JSONs processados e `dashboard/mapa_locais.html` foram gerados, importe o repositório na Vercel e use a raiz do projeto como diretório de publicação.
