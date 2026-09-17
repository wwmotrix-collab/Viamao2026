"""Gera dados do dashboard combinando CSV de seções, CSV resumo e XLSX geográfico."""
import json
import logging
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd

from utils import DataProcessor, DataValidator, ReportGenerator, get_raw_dir, get_processed_dir

logger = logging.getLogger(__name__)


def text(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def key(value: Any) -> str:
    value = unicodedata.normalize("NFKD", text(value)).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]", "", value.lower())


def local_key(value: Any) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKD", text(value)).encode("ascii", "ignore").decode("ascii").lower()).strip()


def integer(value: Any, default: int = 0) -> int:
    try:
        if value is None or pd.isna(value):
            return default
        return int(float(str(value).replace(",", ".")))
    except (TypeError, ValueError):
        return default


def number(value: Any):
    try:
        if value is None or pd.isna(value):
            return None
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def read_csv(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path, encoding="utf-8-sig")
    except UnicodeDecodeError:
        return pd.read_csv(path, encoding="latin-1")


def column(df: pd.DataFrame, *names: str) -> str | None:
    wanted = {key(name) for name in names}
    for col in df.columns:
        if key(col) in wanted:
            return col
    for col in df.columns:
        normalized = key(col)
        if any(wanted_name in normalized for wanted_name in wanted if len(wanted_name) >= 5):
            return col
    return None


def normalize_columns(df: pd.DataFrame) -> Dict[str, str | None]:
    return {
        "zona": column(df, "zona", "zona_eleitoral", "ze"),
        "bairro": column(df, "bairro"),
        "local": column(df, "local", "nome_local", "nome_do_local", "nome do local"),
        "endereco": column(df, "endereco", "logradouro", "rua"),
        "secao": column(df, "secao", "numero_secao", "numero da secao"),
        "denise": column(df, "denise", "votos_denise"),
        "helenir": column(df, "helenir", "votos_helenir"),
        "total": column(df, "total", "total_votos"),
        "eleitores": column(df, "eleitores", "eleitorado", "inscritos", "total_eleitores"),
    }


class DataPipeline:
    def __init__(self, raw_dir: Path = None, processed_dir: Path = None):
        root = Path(__file__).resolve().parent.parent
        self.raw_dir = raw_dir or get_raw_dir()
        self.root = root
        self.processed_dir = processed_dir or get_processed_dir()
        self.processed_dir.mkdir(parents=True, exist_ok=True)

    def _find(self, filename: str) -> Path:
        candidates = [self.raw_dir / filename, self.root / filename]
        for path in candidates:
            if path.exists():
                return path
        raise FileNotFoundError(f"Arquivo não encontrado: {filename}")

    def _load_sections(self) -> Tuple[pd.DataFrame, Dict[str, str | None], Path]:
        path = self._find("tabela_detalhada_secoes_viamao.csv")
        df = read_csv(path)
        cols = normalize_columns(df)
        required = [cols[name] for name in ("local", "secao", "denise", "helenir")]
        if any(value is None for value in required):
            raise ValueError(f"Colunas obrigatórias ausentes no CSV de seções: {list(df.columns)}")
        return df, cols, path

    def _load_summary(self, section_path: Path) -> Dict[str, Dict[str, int]]:
        result: Dict[str, Dict[str, int]] = {}
        paths = list(self.raw_dir.glob("*.csv")) + list(self.root.glob("*.csv"))
        seen = set()
        for path in paths:
            if path in seen or path.resolve() == section_path.resolve():
                continue
            seen.add(path)
            try:
                df = read_csv(path)
            except Exception:
                continue
            cols = normalize_columns(df)
            if not all(cols[name] for name in ("local", "denise", "helenir")):
                continue
            for _, row in df.iterrows():
                name = local_key(row.get(cols["local"]))
                if not name:
                    continue
                result[name] = {
                    "denise": integer(row.get(cols["denise"])),
                    "helenir": integer(row.get(cols["helenir"])),
                    "total": integer(row.get(cols["total"])) if cols["total"] else 0,
                }
        return result

    def _load_xlsx(self) -> Tuple[pd.DataFrame, Dict[str, str], Path]:
        path = self._find("locais_votacao (78).xlsx")
        raw = pd.read_excel(path, header=None)
        header = None
        for index, row in raw.iterrows():
            values = [key(value) for value in row.tolist()]
            if any("latitude" in value for value in values) and any("longitude" in value or "long" in value for value in values):
                header = index
                break
        if header is None:
            raise ValueError("Cabeçalho de coordenadas não encontrado no XLSX")

        headers = []
        for index, value in enumerate(raw.iloc[header].tolist()):
            normalized = key(value)
            if "latitude" in normalized or normalized == "lat": name = "latitude"
            elif "longitude" in normalized or normalized in {"long", "lon"}: name = "longitude"
            elif "nomedolocal" in normalized or normalized in {"local", "nome"}: name = "local"
            elif "endereco" in normalized or "logradouro" in normalized or normalized == "rua": name = "endereco"
            elif "bairro" in normalized: name = "bairro"
            elif normalized in {"zona", "ze"} or "zonaeleitoral" in normalized: name = "zona"
            elif "secao" in normalized: name = "secoes"
            elif "eleitor" in normalized or "inscrit" in normalized: name = "eleitores"
            else: name = f"col_{index}"
            headers.append(name)
        df = raw.iloc[header + 1:].copy()
        df.columns = headers
        return df.dropna(how="all"), {"local": "local", "latitude": "latitude", "longitude": "longitude", "endereco": "endereco", "bairro": "bairro", "zona": "zona", "secoes": "secoes", "eleitores": "eleitores"}, path

    def executar(self) -> bool:
        section_df, cols, section_path = self._load_sections()
        summary = self._load_summary(section_path)
        locations_df, xcols, xlsx_path = self._load_xlsx()

        aggregates: Dict[str, Dict[str, Any]] = {}
        secoes = []
        for _, row in section_df.iterrows():
            name = text(row.get(cols["local"]))
            normalized = local_key(name)
            if not normalized:
                continue
            denise = integer(row.get(cols["denise"]))
            helenir = integer(row.get(cols["helenir"]))
            total = integer(row.get(cols["total"])) if cols["total"] else denise + helenir
            total = total or denise + helenir
            section_number = integer(row.get(cols["secao"]))
            secao = {
                "secao_numero": section_number,
                "zona_eleitoral": integer(row.get(cols["zona"])),
                "bairro": text(row.get(cols["bairro"])) or "N/A",
                "local": name or "N/A",
                "endereco": text(row.get(cols["endereco"])) or "N/A",
                "votos": {"denise": denise, "helenir": helenir, "total": total},
                "percentuais": {"denise": DataProcessor.calcular_percentual(denise, total), "helenir": DataProcessor.calcular_percentual(helenir, total)},
                "abstencoes": None,
                "metadata": {"status": "OK"},
            }
            secoes.append(secao)
            aggregate = aggregates.setdefault(normalized, {"votos_denise": 0, "votos_helenir": 0, "total_votos": 0, "secoes": [], "eleitores": 0})
            aggregate["votos_denise"] += denise
            aggregate["votos_helenir"] += helenir
            aggregate["total_votos"] += total
            aggregate["secoes"].append(section_number)

        locais = []
        for index, row in locations_df.reset_index(drop=True).iterrows():
            nome = text(row.get(xcols["local"]))
            if not nome:
                continue
            normalized = local_key(nome)
            aggregate = aggregates.get(normalized, {"votos_denise": 0, "votos_helenir": 0, "total_votos": 0, "secoes": [], "eleitores": 0})
            resumo = summary.get(normalized, {})
            lat = number(row.get(xcols["latitude"]))
            lon = number(row.get(xcols["longitude"]))
            eleitores = integer(row.get(xcols["eleitores"])) if xcols["eleitores"] in row else 0
            coords = {"latitude": lat, "longitude": lon} if lat is not None and lon is not None else None
            locais.append({
                "id": f"loc_{index:03d}", "nome": nome,
                "endereco": text(row.get(xcols["endereco"])) or "N/A",
                "bairro": text(row.get(xcols["bairro"])) or "N/A",
                "zona_eleitoral": integer(row.get(xcols["zona"])),
                "coordenadas": coords,
                "secoes": sorted(set(aggregate["secoes"])),
                "eleitores": eleitores or resumo.get("eleitores", 0) or None,
                "agregado": {
                    "votos_denise": aggregate["votos_denise"] or resumo.get("denise", 0),
                    "votos_helenir": aggregate["votos_helenir"] or resumo.get("helenir", 0),
                    "total_votos": aggregate["total_votos"] or resumo.get("total", 0),
                    "num_secoes": len(set(aggregate["secoes"])),
                },
                "qualidade_dados": {"anomalias": ["coordenada_ausente"] if coords is None else [], "status": "WARNING" if coords is None else "OK"},
            })

        DataProcessor.save_json({"secoes": secoes}, self.processed_dir / "secoes_normalized.json")
        DataProcessor.save_json({"locais": locais}, self.processed_dir / "locais_normalized.json")
        DataProcessor.save_json({
            "arquivo": "merge_csv_secoes_csv_resumo_xlsx_locais",
            "total_registros_secoes": len(secoes),
            "total_locais_xlsx": len(locations_df),
            "total_locais_exportados": len(locais),
            "locais_com_coordenadas": sum(1 for item in locais if item["coordenadas"]),
            "locais_sem_coordenadas": sum(1 for item in locais if not item["coordenadas"]),
            "total_votos_denise": sum(item["agregado"]["votos_denise"] for item in locais),
            "total_votos_helenir": sum(item["agregado"]["votos_helenir"] for item in locais),
            "total_votos": sum(item["agregado"]["total_votos"] for item in locais),
            "eleitores_disponiveis": any(item["eleitores"] is not None for item in locais),
            "fontes": {"secoes": str(section_path.name), "locais": str(xlsx_path.name)},
        }, self.processed_dir / "relatorio_locais.json")
        logger.info("Pipeline: %s seções, %s locais (%s com coordenadas)", len(secoes), len(locais), sum(1 for item in locais if item["coordenadas"]))
        return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    DataPipeline().executar()
