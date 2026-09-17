"""Utilitários compartilhados pelo pipeline de dados."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Union

logger = logging.getLogger(__name__)


class DataValidator:
    @staticmethod
    def validate_voto(voto: Union[int, float]) -> bool:
        return isinstance(voto, (int, float)) and voto >= 0 and float(voto).is_integer()

    @staticmethod
    def validate_coordenada(lat: float, lon: float) -> bool:
        return -90 <= lat <= 90 and -180 <= lon <= 180 and not (lat == 0 and lon == 0)


class DataProcessor:
    @staticmethod
    def calcular_percentual(valor: Union[int, float], total: Union[int, float]) -> float:
        return round(valor / total * 100, 2) if total else 0.0

    @staticmethod
    def parse_secoes_field(valor: Any) -> List[int]:
        if valor is None:
            return []
        text = str(valor).strip()
        for separator in (';', '|', ','):
            text = text.replace(separator, ' ')
        result = []
        for token in text.split():
            try:
                result.append(int(float(token)))
            except ValueError:
                logger.warning("Seção ignorada: %s", token)
        return sorted(set(result))

    @staticmethod
    def save_json(data: Dict[str, Any], filepath: Path) -> None:
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


class ReportGenerator:
    @staticmethod
    def gerar_relatorio_processamento(arquivo: str, total_registros: int,
                                      registros_ok: int, warnings=None, erros=None) -> Dict[str, Any]:
        warnings = warnings or []
        erros = erros or []
        return {
            'arquivo': arquivo,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'total_registros': total_registros,
            'registros_ok': registros_ok,
            'registros_com_warning': len(warnings),
            'registros_com_erro': len(erros),
            'taxa_sucesso': round(registros_ok / total_registros * 100, 2) if total_registros else 0,
            'warnings': warnings[:100],
            'erros': erros[:100],
        }


def get_data_dir() -> Path:
    return Path(__file__).resolve().parent.parent / 'data'


def get_raw_dir() -> Path:
    root_dir = Path(__file__).resolve().parent.parent
    default_dir = get_data_dir() / 'raw'
    if default_dir.exists():
        return default_dir

    raw_candidates = [
        root_dir / 'tabela_detalhada_secoes_viamao.csv',
        root_dir / 'locais_votacao (78).xlsx',
        root_dir / 'viamao_2024.csv',
    ]
    if any(candidate.exists() for candidate in raw_candidates):
        return root_dir
    return default_dir


def get_processed_dir() -> Path:
    processed_path = get_data_dir() / 'processed'
    processed_path.mkdir(parents=True, exist_ok=True)
    return processed_path
