"""Processa seções e os 78 locais de votação para o dashboard."""
import logging
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd

from utils import DataProcessor, DataValidator, ReportGenerator, get_raw_dir, get_processed_dir

logger = logging.getLogger(__name__)


def _text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ''
    return str(value).strip()


def _number(value: Any, default: int = 0) -> int:
    try:
        if value is None or pd.isna(value):
            return default
        return int(float(str(value).replace(',', '.')))
    except (TypeError, ValueError):
        return default


def _key(value: Any) -> str:
    text = unicodedata.normalize('NFKD', _text(value)).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]', '', text.lower())


def _coord(value: Any):
    text = _text(value).replace('−', '-').replace(',', '.')
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _first(row: Dict, names: List[str], default=''):
    for name, value in row.items():
        if _key(name) in names or any(token in _key(name) for token in names if len(token) > 5):
            if _text(value):
                return value
    return default


def _name_key(value: Any) -> str:
    return _key(value)


class SecaoProcessor:
    def __init__(self):
        self.secoes_raw, self.secoes_normalized, self.relatorio = [], [], {}

    def carregar_csv(self, filepath: Path) -> bool:
        try:
            try:
                df = pd.read_csv(filepath, encoding='utf-8-sig')
            except UnicodeDecodeError:
                df = pd.read_csv(filepath, encoding='latin-1')
            df.columns = [_text(c).lower().strip() for c in df.columns]
            self.secoes_raw = df.to_dict('records')
            logger.info('Carregado: %s (%s registros)', filepath.name, len(df))
            return True
        except Exception as exc:
            logger.error('Erro ao carregar %s: %s', filepath, exc)
            return False

    def processar(self) -> Tuple[List[Dict], Dict]:
        erros = []
        for idx, sec in enumerate(self.secoes_raw):
            try:
                item = self._normalizar_secao(sec, idx)
                if item:
                    self.secoes_normalized.append(item)
                else:
                    erros.append(f'Seção {idx}: falha na normalização')
            except Exception as exc:
                erros.append(f'Seção {idx}: {exc}')
        self.relatorio = ReportGenerator.gerar_relatorio_processamento(
            'tabela_detalhada_secoes_viamao.csv', len(self.secoes_raw),
            len(self.secoes_normalized), erros=erros)
        logger.info('Processadas %s/%s seções', len(self.secoes_normalized), len(self.secoes_raw))
        return self.secoes_normalized, self.relatorio

    def _normalizar_secao(self, sec: Dict, idx: int) -> Dict:
        secao = _number(_first(sec, ['secao', 'numerosecao']), idx)
        denise = _number(_first(sec, ['votosdenise', 'denise']))
        helenir = _number(_first(sec, ['votoshelenir', 'helenir']))
        total = denise + helenir
        if not (DataProcessor and DataValidator.validate_voto(denise) and DataValidator.validate_voto(helenir)):
            return None
        return {
            'secao_numero': secao,
            'zona_eleitoral': _number(_first(sec, ['zonaeleitoral', 'zona', 'ze'])),
            'bairro': _text(_first(sec, ['bairro'])) or 'N/A',
            'local': _text(_first(sec, ['local', 'nomelocal', 'nomedolocal'])) or 'N/A',
            'endereco': _text(_first(sec, ['endereco'])) or 'N/A',
            'votos': {'denise': denise, 'helenir': helenir, 'total': total},
            'percentuais': {
                'denise': DataProcessor.calcular_percentual(denise, total),
                'helenir': DataProcessor.calcular_percentual(helenir, total)},
            'metadata': {'status': 'OK'}
        }


class LocaisProcessor:
    def __init__(self):
        self.locais_raw, self.locais_normalized, self.relatorio = [], [], {}

    def carregar_xlsx(self, filepath: Path) -> bool:
        try:
            raw = pd.read_excel(filepath, header=None)
            header_index = None
            for index, row in raw.iterrows():
                keys = [_key(v) for v in row.tolist()]
                if any('nomedolocal' in v or 'nomedolocaldevotacao' in v for v in keys) and any('latitude' in v for v in keys):
                    header_index = index
                    break
            if header_index is None:
                raise ValueError('Cabeçalho do XLSX não encontrado')
            headers = [_text(v) or f'col_{i}' for i, v in enumerate(raw.iloc[header_index].tolist())]
            df = raw.iloc[header_index + 1:].copy()
            df.columns = headers
            df = df.dropna(how='all')
            self.locais_raw = df.to_dict('records')
            logger.info('Carregado: %s (%s registros; cabeçalho na linha %s)', filepath.name, len(df), header_index)
            return True
        except Exception as exc:
            logger.error('Erro ao carregar %s: %s', filepath, exc)
            return False

    def processar(self, secoes: List[Dict]) -> Tuple[List[Dict], Dict]:
        por_local: Dict[str, Dict] = {}
        for sec in secoes:
            key = _name_key(sec.get('local'))
            if not key or key == 'na':
                continue
            item = por_local.setdefault(key, {'denise': 0, 'helenir': 0, 'total': 0, 'secoes': [], 'eleitores': 0})
            item['denise'] += sec['votos']['denise']
            item['helenir'] += sec['votos']['helenir']
            item['total'] += sec['votos']['total']
            item['secoes'].append(sec['secao_numero'])

        warnings, erros = [], []
        for idx, row in enumerate(self.locais_raw):
            try:
                item = self._normalizar_local(row, idx, por_local)
                if item:
                    self.locais_normalized.append(item)
                else:
                    warnings.append(f'Local {idx}: registro sem nome ou coordenada válida')
            except Exception as exc:
                erros.append(f'Local {idx}: {exc}')

        self.relatorio = ReportGenerator.gerar_relatorio_processamento(
            'locais_votacao (78).xlsx', len(self.locais_raw), len(self.locais_normalized), warnings, erros)
        logger.info('Processados %s/%s locais', len(self.locais_normalized), len(self.locais_raw))
        return self.locais_normalized, self.relatorio

    def _normalizar_local(self, row: Dict, idx: int, por_local: Dict) -> Dict:
        nome = _text(_first(row, ['nomedolocaldevotacao', 'nomedolocal', 'local']))
        lat = _coord(_first(row, ['latitude', 'lat']))
        lon = _coord(_first(row, ['longitude', 'long']))
        if not nome or lat is None or lon is None or not DataValidator.validate_coordenada(lat, lon):
            return None
        agregado = por_local.get(_name_key(nome), {'denise': 0, 'helenir': 0, 'total': 0, 'secoes': []})
        secoes_xlsx = DataProcessor.parse_secoes_field(_first(row, ['secoes', 'secao']))
        secoes = sorted(set(secoes_xlsx or agregado['secoes']))
        eleitores = _number(_first(row, ['eleitores', 'eleitorado', 'totaldeeleitores']))
        return {
            'id': f'loc_{idx:03d}', 'nome': nome,
            'endereco': _text(_first(row, ['endereco'])) or 'N/A',
            'zona_eleitoral': _number(_first(row, ['ze', 'zona', 'zonaeleitoral'])),
            'bairro': _text(_first(row, ['bairro'])) or 'N/A',
            'eleitores': eleitores,
            'coordenadas': {'latitude': lat, 'longitude': lon},
            'secoes': secoes,
            'agregado': {
                'votos_denise': agregado['denise'], 'votos_helenir': agregado['helenir'],
                'total_votos': agregado['total'], 'num_secoes': len(secoes)},
            'qualidade_dados': {'anomalias': ['multiplas_secoes_em_um_registro'] if len(secoes_xlsx) > 1 else [], 'status': 'OK'}
        }


class DataPipeline:
    def __init__(self, raw_dir=None, processed_dir=None):
        self.raw_dir = raw_dir or get_raw_dir()
        self.processed_dir = processed_dir or get_processed_dir()
        self.processed_dir.mkdir(parents=True, exist_ok=True)

    def executar(self) -> bool:
        sec = SecaoProcessor()
        if not sec.carregar_csv(self.raw_dir / 'tabela_detalhada_secoes_viamao.csv'):
            return False
        secoes, rel_sec = sec.processar()
        DataProcessor.save_json({'secoes': secoes}, self.processed_dir / 'secoes_normalized.json')
        DataProcessor.save_json(rel_sec, self.processed_dir / 'relatorio_secoes.json')
        loc = LocaisProcessor()
        if not loc.carregar_xlsx(self.raw_dir / 'locais_votacao (78).xlsx'):
            return False
        locais, rel_loc = loc.processar(secoes)
        DataProcessor.save_json({'locais': locais}, self.processed_dir / 'locais_normalized.json')
        DataProcessor.save_json(rel_loc, self.processed_dir / 'relatorio_locais.json')
        logger.info('Pipeline concluído: %s seções e %s locais', len(secoes), len(locais))
        return True


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    DataPipeline().executar()
