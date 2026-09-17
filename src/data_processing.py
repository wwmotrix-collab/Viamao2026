"""Processa seções e locais de votação para o dashboard."""
import logging
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd

from utils import DataProcessor, DataValidator, ReportGenerator, get_raw_dir, get_processed_dir

logger = logging.getLogger(__name__)


def _text(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def _number(value: Any, default: int = 0) -> int:
    try:
        if value is None or pd.isna(value):
            return default
        return int(float(str(value).replace(",", ".")))
    except (TypeError, ValueError):
        return default


def _normalize_key(value: Any) -> str:
    text = unicodedata.normalize("NFKD", _text(value)).encode("ascii", "ignore").decode("utf-8")
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _coord(value: Any) -> float | None:
    text = _text(value).replace("−", "-").replace(",", ".")
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _first(row: Dict[str, Any], candidates: List[str]) -> Any:
    for key, value in row.items():
        if _normalize_key(key) in {_normalize_key(candidate) for candidate in candidates}:
            return value
    for candidate in candidates:
        if candidate in row:
            return row[candidate]
    for key, value in row.items():
        key_norm = _normalize_key(key)
        for candidate in candidates:
            if _normalize_key(candidate) in key_norm or key_norm in _normalize_key(candidate):
                return value
    return None


class SecaoProcessor:
    def __init__(self):
        self.secoes_raw = []
        self.secoes_normalized = []
        self.relatorio = {}

    def carregar_csv(self, filepath: Path) -> bool:
        try:
            try:
                df = pd.read_csv(filepath, encoding="utf-8-sig")
            except UnicodeDecodeError:
                df = pd.read_csv(filepath, encoding="latin-1")
            df.columns = [_text(col).lower().strip() for col in df.columns]
            self.secoes_raw = df.to_dict("records")
            logger.info("Carregado: %s (%s registros)", filepath.name, len(df))
            return True
        except Exception as exc:
            logger.error("Erro ao carregar %s: %s", filepath, exc)
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
                    erros.append(f"Seção {idx}: falha na normalização")
            except Exception as exc:
                erros.append(f"Seção {idx}: {exc}")
        self.relatorio = ReportGenerator.gerar_relatorio_processamento(
            "tabela_detalhada_secoes_viamao.csv",
            len(self.secoes_raw),
            len(self.secoes_normalized),
            erros=erros,
        )
        logger.info("Processadas %s/%s seções", len(self.secoes_normalized), len(self.secoes_raw))
        return self.secoes_normalized, self.relatorio

    def _normalizar_secao(self, sec: Dict, idx: int) -> Dict:
        secao_num = _number(_first(sec, ["secao", "numero_secao", "numerosecao"])) or idx
        votos_denise = _number(_first(sec, ["votos_denise", "denise", "votosdenise"]))
        votos_helenir = _number(_first(sec, ["votos_helenir", "helenir", "votoshelenir"]))
        if not (DataValidator.validate_voto(votos_denise) and DataValidator.validate_voto(votos_helenir)):
            return None
        total = votos_denise + votos_helenir
        return {
            "secao_numero": secao_num,
            "zona_eleitoral": _number(_first(sec, ["zona_eleitoral", "zona", "ze", "zonaeleitoral"])),
            "bairro": _text(_first(sec, ["bairro"])) or "N/A",
            "local": _text(_first(sec, ["local", "nome_local", "nomedolocal", "nomelocal"])) or "N/A",
            "endereco": _text(_first(sec, ["endereco"])) or "N/A",
            "votos": {"denise": votos_denise, "helenir": votos_helenir, "total": total},
            "percentuais": {
                "denise": DataProcessor.calcular_percentual(votos_denise, total),
                "helenir": DataProcessor.calcular_percentual(votos_helenir, total),
            },
            "abstencoes": None,
            "metadata": {"status": "OK"},
        }


class LocaisProcessor:
    def __init__(self):
        self.locais_raw = []
        self.locais_normalized = []
        self.relatorio = {}

    def carregar_xlsx(self, filepath: Path) -> bool:
        try:
            raw = pd.read_excel(filepath, header=None)
            header_index = None
            for index, row in raw.iterrows():
                values = [_normalize_key(value) for value in row.tolist()]
                has_local = any("nomedolocal" in v or "local" in v or "nome" in v for v in values)
                has_lat = any("latitude" in v or "lat" in v for v in values)
                has_lon = any("longitude" in v or "long" in v or "lon" in v for v in values)
                if has_local and has_lat and has_lon:
                    header_index = index
                    break

            if header_index is None:
                raise ValueError("Cabeçalho com Nome do Local/Latitude/Longitude não encontrado")

            column_names = []
            for i, value in enumerate(raw.iloc[header_index].tolist()):
                label = _text(value)
                norm = _normalize_key(label)
                if not label:
                    column_names.append(f"col_{i}")
                elif "nomedolocal" in norm or "nome" in norm or "local" in norm:
                    column_names.append("local")
                elif "latitude" in norm or "lat" in norm:
                    column_names.append("latitude")
                elif "longitude" in norm or "long" in norm or "lon" in norm:
                    column_names.append("longitude")
                elif "bairro" in norm:
                    column_names.append("bairro")
                elif "endereco" in norm or "rua" in norm:
                    column_names.append("endereco")
                elif "zona" in norm or "ze" in norm:
                    column_names.append("zona")
                elif "secoes" in norm or "secao" in norm:
                    column_names.append("secoes")
                elif "eleitor" in norm:
                    column_names.append("eleitores")
                else:
                    column_names.append(f"col_{i}")

            df = raw.iloc[header_index + 1 :].copy()
            df.columns = column_names
            df = df.dropna(how="all")
            df = df.loc[:, [col for col in df.columns if col]]
            self.locais_raw = df.to_dict("records")
            logger.info("Carregado: %s (%s registros; cabeçalho na linha %s)", filepath.name, len(df), header_index)
            return True
        except Exception as exc:
            logger.error("Erro ao carregar %s: %s", filepath, exc)
            return False

    def processar(self, secoes_normalized: List[Dict] = None) -> Tuple[List[Dict], Dict]:
        self.locais_normalized = []
        warnings, erros = [], []
        por_local: Dict[str, Dict] = {}

        for sec in secoes_normalized or []:
            nome = _text(sec.get("local"))
            key = _normalize_key(nome)
            if not key:
                continue
            entry = por_local.setdefault(key, {"votos_denise": 0, "votos_helenir": 0, "total_votos": 0, "secoes": []})
            entry["votos_denise"] += sec["votos"]["denise"]
            entry["votos_helenir"] += sec["votos"]["helenir"]
            entry["total_votos"] += sec["votos"]["total"]
            entry["secoes"].append(sec["secao_numero"])

        for idx, local in enumerate(self.locais_raw):
            try:
                normalized = self._normalizar_local(local, idx, por_local)
                if normalized:
                    self.locais_normalized.append(normalized)
                else:
                    warnings.append(f"Local {idx}: coordenadas ou nome inválido")
            except Exception as exc:
                erros.append(f"Local {idx}: {exc}")

        self.relatorio = ReportGenerator.gerar_relatorio_processamento(
            "locais_votacao (78).xlsx",
            len(self.locais_raw),
            len(self.locais_normalized),
            warnings,
            erros,
        )
        logger.info("Processados %s/%s locais", len(self.locais_normalized), len(self.locais_raw))
        return self.locais_normalized, self.relatorio

    def _normalizar_local(self, local: Dict, idx: int, por_local: Dict) -> Dict:
        nome = _text(_first(local, ["local", "nome", "nomedolocal", "nome_local"]))
        if not nome:
            return None

        lat = _coord(_first(local, ["latitude", "lat"]))
        lon = _coord(_first(local, ["longitude", "long", "lon"]))
        if lat is None or lon is None or not DataValidator.validate_coordenada(lat, lon):
            return None

        key = _normalize_key(nome)
        agregado = por_local.get(key, {"votos_denise": 0, "votos_helenir": 0, "total_votos": 0, "secoes": []})
        secoes_xlsx = DataProcessor.parse_secoes_field(_first(local, ["secoes", "secao", "secao_final"]))
        secoes = sorted(set((secoes_xlsx or []) + (agregado.get("secoes", []) or [])))
        eleitores = _number(_first(local, ["eleitores", "eleitorado", "totaldeeleitores", "total_eleitores"]))
        total = agregado.get("total_votos", 0)

        return {
            "id": f"loc_{idx:03d}",
            "nome": nome,
            "endereco": _text(_first(local, ["endereco", "rua"])) or "N/A",
            "zona_eleitoral": _number(_first(local, ["zona_eleitoral", "zona", "ze"])),
            "bairro": _text(_first(local, ["bairro"])) or "N/A",
            "eleitores": eleitores,
            "coordenadas": {"latitude": lat, "longitude": lon},
            "secoes": secoes,
            "agregado": {
                "votos_denise": agregado.get("votos_denise", 0),
                "votos_helenir": agregado.get("votos_helenir", 0),
                "total_votos": total,
                "num_secoes": len(secoes),
            },
            "qualidade_dados": {
                "anomalias": ["multiplas_secoes_em_um_registro"] if len(secoes_xlsx) > 1 else [],
                "status": "OK",
            },
        }


class DataPipeline:
    def __init__(self, raw_dir: Path = None, processed_dir: Path = None):
        self.raw_dir = raw_dir or get_raw_dir()
        self.processed_dir = processed_dir or get_processed_dir()
        self.processed_dir.mkdir(parents=True, exist_ok=True)

    def executar(self) -> bool:
        sec = SecaoProcessor()
        csv_path = self.raw_dir / "tabela_detalhada_secoes_viamao.csv"
        xlsx_path = self.raw_dir / "locais_votacao (78).xlsx"
        if not sec.carregar_csv(csv_path):
            return False
        secoes, relatorio_secoes = sec.processar()
        DataProcessor.save_json({"secoes": secoes}, self.processed_dir / "secoes_normalized.json")
        DataProcessor.save_json(relatorio_secoes, self.processed_dir / "relatorio_secoes.json")

        locais_processor = LocaisProcessor()
        if not locais_processor.carregar_xlsx(xlsx_path):
            return False
        locais, relatorio_locais = locais_processor.processar(secoes)
        DataProcessor.save_json({"locais": locais}, self.processed_dir / "locais_normalized.json")
        DataProcessor.save_json(relatorio_locais, self.processed_dir / "relatorio_locais.json")
        logger.info("Pipeline concluído: %s seções e %s locais", len(secoes), len(locais))
        return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    DataPipeline().executar()

