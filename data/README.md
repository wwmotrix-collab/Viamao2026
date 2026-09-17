# Diretório de Dados

## Estrutura

```
data/
├── raw/
│   ├── viamao_2024.csv                    # Dados brutos de votação (21 MB)
│   ├── tabela_detalhada_secoes_viamao.csv # Seções normalizadas (40 KB)
│   └── locais_votacao (78).xlsx           # Coordenadas dos locais (15 KB)
└── processed/
    ├── secoes_normalized.json              # Seções processadas e validadas
    ├── locais_normalized.json              # Locais com agregações
    ├── similarity_analysis.json            # Análise de padrões de similaridade
    ├── relatorio_secoes.json               # Relatório de processamento
    └── relatorio_locais.json               # Relatório de processamento
```

## Dados Brutos (raw/)

### viamao_2024.csv
Arquivo histórico com dados de votação completos. A ser analisado durante processamento.

**Tamanho**: 21 MB

### tabela_detalhada_secoes_viamao.csv
Dados normalizados por seção eleitoral.

**Colunas esperadas**:
- zona_eleitoral
- bairro
- local
- endereco
- secao
- votos_denise
- votos_helenir
- (total é calculado automaticamente)

**Tamanho**: ~40 KB

### locais_votacao (78).xlsx
Coordenadas geográficas dos 78 locais de votação.

**Colunas esperadas**:
- local
- latitude
- longitude
- secoes (pode conter múltiplos valores separados por vírgula ou ponto-e-vírgula)

**Tamanho**: ~15 KB

⚠️ **Nota**: Últimos registros contêm anomalias (múltiplas seções por linha).

---

## Dados Processados (processed/)

Gerados automaticamente pelo pipeline `src/data_processing.py`.

### secoes_normalized.json

Seções eleitorais normalizadas e validadas.

```json
{
  "secoes": [
    {
      "secao_numero": 1,
      "zona_eleitoral": 1,
      "bairro": "Centro",
      "local": "EMEF Anita Garibaldi",
      "endereco": "Rua das Flores 123",
      "votos": {
        "denise": 45,
        "helenir": 32,
        "total": 77
      },
      "percentuais": {
        "denise": 58.44,
        "helenir": 41.56
      },
      "metadata": {
        "processado_em": "2026-09-16T14:30:00Z",
        "status": "OK"
      }
    }
  ]
}
```

### locais_normalized.json

Locais de votação com coordenadas e agregações por local.

```json
{
  "locais": [
    {
      "id": "loc_001",
      "nome": "EMEF Anita Garibaldi",
      "endereco": "Rua das Flores 123",
      "zona_eleitoral": 1,
      "bairro": "Centro",
      "coordenadas": {
        "latitude": -29.8456,
        "longitude": -51.3212
      },
      "secoes": [1, 2, 15],
      "agregado": {
        "votos_denise": 145,
        "votos_helenir": 98,
        "total_votos": 243,
        "num_secoes": 3
      },
      "marcador": {
        "tamanho": "medium",
        "intensidade": 0.75,
        "cor": "#FF6B6B"
      },
      "qualidade_dados": {
        "anomalias": [],
        "status": "OK"
      }
    }
  ]
}
```

### similarity_analysis.json

Análise de padrões e similaridade entre seções (gerado por `src/similarity_analysis.py`).

```json
{
  "analise_global": {
    "total_secoes": 145,
    "data_geracao": "2026-09-16T14:30:00Z"
  },
  "padroes": [
    {
      "padrao_id": "P001",
      "nome": "Maioria Denise - Zona Centro",
      "caracteristicas": {
        "zona_eleitoral": 1,
        "percentual_denise_min": 55.0,
        "percentual_denise_max": 70.0
      },
      "secoes_principais": [1, 2, 5],
      "secoes_similares": [
        {
          "secao": 10,
          "similaridade": 0.92,
          "motivo": "Mesma zona, percentual próximo"
        }
      ]
    }
  ]
}
```

### relatorio_secoes.json

Relatório de processamento do arquivo de seções.

```json
{
  "arquivo": "tabela_detalhada_secoes_viamao.csv",
  "timestamp": "2026-09-16T14:30:00Z",
  "total_registros": 150,
  "registros_ok": 145,
  "registros_com_warning": 5,
  "registros_com_erro": 0,
  "taxa_sucesso": 96.67,
  "warnings": [
    "Seção 134: votos = 0 (possível erro de digitação)"
  ],
  "erros": []
}
```

### relatorio_locais.json

Relatório de processamento do arquivo de locais.

```json
{
  "arquivo": "locais_votacao.xlsx",
  "timestamp": "2026-09-16T14:30:00Z",
  "total_registros": 78,
  "registros_ok": 75,
  "registros_com_warning": 3,
  "registros_com_erro": 0,
  "taxa_sucesso": 96.15,
  "warnings": [
    "Local 72: múltiplas seções em um registro"
  ],
  "erros": []
}
```

---

## Como Usar

### Gerar dados processados

```bash
cd src
python data_processing.py
```

Isso vai:
1. Carregar `tabela_detalhada_secoes_viamao.csv`
2. Normalizar e validar seções
3. Carregar `locais_votacao.xlsx`
4. Normalizar e validar locais
5. Mesclar dados
6. Exportar JSONs em `processed/`

### Usar dados no dashboard

```javascript
// Carregar seções
fetch('data/processed/secoes_normalized.json')
  .then(r => r.json())
  .then(data => console.log(data.secoes));

// Carregar locais
fetch('data/processed/locais_normalized.json')
  .then(r => r.json())
  .then(data => console.log(data.locais));
```

---

## Qualidade dos Dados

Veja `docs/DATA_SCHEMA.md` para:
- Validação de campos
- Tratamento de anomalias
- Mapeamento de relacionamentos
- Regras de agregação
