"""
Pipeline de processamento de dados eleitorais.

Lê a tabela de seções e o XLSX de coordenadas, que possui linhas
instrutivas antes do cabeçalho real, e gera JSONs para o dashboard.
"""

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd

from utils import DataProcessor, DataValidator, ReportGenerator, get_raw_dir, get_processed_dir

logger = logging.getLogger(__name__)


def _text(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ''
    return str(value).strip()


def _number(value: Any, default: int = 0) -> int:
    try:
        if pd.isna(value):
            return default
        return int(float(str(value).replace(',', '.')))
    except (TypeError, ValueError):
        return default


def _key(value: Any) -> str:
    return re.sub(r'[^a-z0-9]', '', _text(value).lower())


class SecaoProcessor:
    def __init__(self):
        self.secoes_raw = []
        self.secoes_normalized = []
        self.relatorio = {}

    def carregar_csv(self, filepath: Path) -> bool:
        try:
            df = pd.read_csv(filepath, encoding='utf-8-sig')
            df.columns = [_text(col).lower().strip() for col in df.columns]
            self.secoes_raw = df.to_dict('records')
            logger.info('Carregado: %s (%s registros)', filepath.name, len(df))
            return True
        except UnicodeDecodeError:
            df = pd.read_csv(filepath, encoding='latin-1')
            df.columns = [_text(col).lower().strip() for col in df.columns]
            self.secoes_raw = df.to_dict('records')
            return True
        except Exception as exc:
            logger.error('Erro ao carregar %s: %s', filepath, exc)
            return False

    def processar(self) -> Tuple[List[Dict], Dict]:
        self.secoes_normalized = []
        erros = []
        for idx, sec in enumerate(self.secoes_raw):
            try:
                normalized = self._normalizar_secao(sec, idx)
                if normalized:
                    self.secoes_normalized.append(normalized)
                else:
                    erros.append(f'Seção {idx}: falha na normalização')
            except Exception as exc:
                erros.append(f'Seção {idx}: {exc}')
        self.relatorio = ReportGenerator.gerar_relatorio_processamento(
            'tabela_detalhada_secoes_viamao.csv', len(self.secoes_raw),
            len(self.secoes_normalized), erros=erros
        )
        logger.info('Processadas %s/%s seções', len(self.secoes_normalized), len(self.secoes_raw))
        return self.secoes_normalized, self.relatorio

    def _normalizar_secao(self, sec: Dict, idx: int) -> Dict:
        secao_num = _number(sec.get('secao') or sec.get('numero_secao'), idx)
        votos_denise = _number(sec.get('votos_denise') or sec.get('denise'))
        votos_helenir = _number(sec.get('votos_helenir') or sec.get('helenir'))
        if not (DataValidator.validate_voto(votos_denise) and DataValidator.validate_voto(votos_helenir)):
            return None
        total = votos_denise + votos_helenir
        return {
            'secao_numero': secao_num,
            'zona_eleitoral': _number(sec.get('zona_eleitoral') or sec.get('zona')),
            'bairro': _text(sec.get('bairro')) or 'N/A',
            'local': _text(sec.get('local') or sec.get('nome_local')) or 'N/A',
            'endereco': _text(sec.get('endereco')) or 'N/A',
            'votos': {'denise': votos_denise, 'helenir': votos_helenir, 'total': total},
            'percentuais': {
                'denise': DataProcessor.calcular_percentual(votos_denise, total),
                'helenir': DataProcessor.calcular_percentual(votos_helenir, total),
            },
            'abstencoes': None,
            'metadata': {'status': 'OK'},
        }


class LocaisProcessor:
    def __init__(self):
        self.locais_raw = []
        self.locais_normalized = []
        self.relatorio = {}

    def carregar_xlsx(self, filepath: Path) -> bool:
        try:
            # O arquivo tem título/instruções antes do cabeçalho real.
            raw = pd.read_excel(filepath, header=None)
            header_index = None
            for index, row in raw.iterrows():
                values = [_key(value) for value in row.tolist()]
                if any('nomedolocal' in value for value in values) or (
                    'latitude' in values and 'longitude' in values
                ):
                    header_index = index
                    break

            if header_index is None:
                raise ValueError('Cabeçalho com Nome do Local/Latitude/Longitude não encontrado')

            headers = [_text(value) for value in raw.iloc[header_index].tolist()]
            df = raw.iloc[header_index + 1:].copy()
            df.columns = headers
            df = df.dropna(how='all')

            # Remove colunas sem nome e cria aliases estáveis.
            df = df.loc[:, [column for column in df.columns if column]]
            aliases = {}
            for column in df.columns:
                normalized = _key(column)
                if 'nomedolocal' in normalized:
                    aliases[column] = 'local'
                elif normalized in ('latitude', 'lat'):
                    aliases[column] = 'latitude'
                elif normalized in ('longitude', 'lon', 'long'):
                    aliases[column] = 'longitude'
                elif normalized in ('ze', 'zona', 'zonaeleitoral'):
                    aliases[column] = 'zona'
                elif 'secoes' in normalized or 'secao' in normalized:
                    aliases[column] = 'secoes'
            df = df.rename(columns=aliases)
            self.locais_raw = df.to_dict('records')
            logger.info('Carregado: %s (%s registros; cabeçalho na linha %s)', filepath.name, len(df), header_index)
            return True
        except Exception as exc:
            logger.error('Erro ao carregar %s: %s', filepath, exc)
            return False

    def processar(self, secoes_normalized: List[Dict] = None) -> Tuple[List[Dict], Dict]:
        self.locais_normalized = []
        warnings, erros = [], []
        por_local: Dict[str, Dict] = {}
        for sec in secoes_normalized or []:
            name = _text(sec.get('local')).casefold()
            if not name:
                continue
            entry = por_local.setdefault(name, {'votos_denise': 0, 'votos_helenir': 0, 'total_votos': 0, 'secoes': []})
            entry['votos_denise'] += sec['votos']['denise']
            entry['votos_helenir'] += sec['votos']['helenir']
            entry['total_votos'] += sec['votos']['total']
            entry['secoes'].append(sec['secao_numero'])

        for idx, local in enumerate(self.locais_raw):
            try:
                normalized = self._normalizar_local(local, idx, por_local)
                if normalized:
                    self.locais_normalized.append(normalized)
                else:
                    warnings.append(f'Local {idx}: coordenadas ou nome inválido')
            except Exception as exc:
                erros.append(f'Local {idx}: {exc}')

        self.relatorio = ReportGenerator.gerar_relatorio_processamento(
            'locais_votacao (78).xlsx', len(self.locais_raw),
            len(self.locais_normalized), warnings, erros
        )
        logger.info('Processados %s/%s locais', len(self.locais_normalized), len(self.locais_raw))
        return self.locais_normalized, self.relatorio

    def _normalizar_local(self, local: Dict, idx: int, por_local: Dict) -> Dict:
        name = _text(local.get('local')) or 'N/A'
        try:
            lat = float(str(local.get('latitude')).replace(',', '.'))
            lon = float(str(local.get('longitude')).replace(',', '.'))
        except (TypeError, ValueError):
            return None
        if not DataValidator.validate_coordenada(lat, lon):
            return None

        key = name.casefold()
        agregado = por_local.get(key, {'votos_denise': 0, 'votos_helenir': 0, 'total_votos': 0, 'secoes': []})
        secoes_xlsx = DataProcessor.parse_secoes_field(local.get('secoes'))
        secoes = sorted(set(secoes_xlsx or agregado['secoes']))
        anomalias = ['multiplas_secoes_em_um_registro'] if len(secoes_xlsx) > 1 else []
        total = agregado['total_votos']
        return {
            'id': f'loc_{idx:03d}', 'nome': name,
            'endereco': _text(local.get('endereco')) or 'N/A',
            'zona_eleitoral': _number(local.get('zona')),
            'bairro': _text(local.get('bairro')) or 'N/A',
            'coordenadas': {'latitude': lat, 'longitude': lon},
            'secoes': secoes,
            'agregado': {
                'votos_denise': agregado['votos_denise'],
                'votos_helenir': agregado['votos_helenir'],
                'total_votos': total,
                'num_secoes': len(secoes),
            },
            'qualidade_dados': {'anomalias': anomalias, 'status': 'WARNING' if anomalias else 'OK'},
        }


class DataPipeline:
    def __init__(self, raw_dir: Path = None, processed_dir: Path = None):
        self.raw_dir = raw_dir or get_raw_dir()
        self.processed_dir = processed_dir or get_processed_dir()
        self.processed_dir.mkdir(parents=True, exist_ok=True)

    def executar(self) -> bool:
        sec = SecaoProcessor()
        csv_path = self.raw_dir / 'tabela_detalhada_secoes_viamao.csv'
        xlsx_path = self.raw_dir / 'locais_votacao (78).xlsx'
        if not sec.carregar_csv(csv_path):
            return False
        secoes, relatorio_secoes = sec.processar()
        DataProcessor.save_json({'secoes': secoes}, self.processed_dir / 'secoes_normalized.json')
        DataProcessor.save_json(relatorio_secoes, self.processed_dir / 'relatorio_secoes.json')

        locais_processor = LocaisProcessor()
        if not locais_processor.carregar_xlsx(xlsx_path):
            return False
        locais, relatorio_locais = locais_processor.processar(secoes)
        DataProcessor.save_json({'locais': locais}, self.processed_dir / 'locais_normalized.json')
        DataProcessor.save_json(relatorio_locais, self.processed_dir / 'relatorio_locais.json')
        logger.info('Pipeline concluído: %s seções e %s locais', len(secoes), len(locais))
        return True


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    DataPipeline().executar()
