"""Gera mapa interativo de locais de votação."""

import json
import logging
from pathlib import Path
from typing import Dict, List

import folium

logger = logging.getLogger(__name__)


class MapBuilder:
    """Constrói mapa interativo com locais e seções."""

    def __init__(self, locais_path: Path, output_path: Path):
        self.locais_path = locais_path
        self.output_path = output_path
        self.locais = []

    def load(self) -> List[Dict]:
        """Carrega dados de locais."""
        with open(self.locais_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self.locais = data.get('locais', [])
        logger.info(f"Carregados {len(self.locais)} locais")
        return self.locais

    def build(self) -> folium.Map:
        """Gera mapa Folium."""
        if not self.locais:
            self.load()

        # Centralizar no município
        mapa = folium.Map(location=[-30.084, -51.023], zoom_start=11, tiles='OpenStreetMap')

        for local in self.locais:
            coords = local.get('coordenadas', {})
            lat = coords.get('latitude')
            lon = coords.get('longitude')

            if lat is None or lon is None:
                continue

            agregado = local.get('agregado', {})
            total = agregado.get('total_votos', 0)
            votos_denise = agregado.get('votos_denise', 0)
            votos_helenir = agregado.get('votos_helenir', 0)

            raio = max(8, min(36, total / 3))
            cor = '#FF6B6B' if votos_denise >= votos_helenir else '#4ECDC4'

            popup_html = f"""
            <div style='width:220px;'>
                <b>{local.get('nome', 'Local')}</b><br>
                Bairro: {local.get('bairro', 'N/A')}<br>
                Zona: {local.get('zona_eleitoral', 'N/A')}<br>
                Seções: {local.get('secoes', [])}<br>
                <hr>
                Denise: <b>{votos_denise}</b><br>
                Helenir: <b>{votos_helenir}</b><br>
                Total: <b>{total}</b>
            </div>
            """

            folium.CircleMarker(
                location=[lat, lon],
                radius=raio / 2,
                color=cor,
                fill=True,
                fill_color=cor,
                fill_opacity=0.75,
                popup=folium.Popup(popup_html, max_width=300),
                tooltip=f"{local.get('nome', 'Local')} - {total} votos"
            ).add_to(mapa)

        return mapa

    def save(self) -> Path:
        """Salva mapa HTML."""
        mapa = self.build()
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        mapa.save(str(self.output_path))
        logger.info(f"Mapa salvo em {self.output_path}")
        return self.output_path


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    base = Path(__file__).resolve().parent.parent
    builder = MapBuilder(
        locais_path=base / 'data' / 'processed' / 'locais_normalized.json',
        output_path=base / 'dashboard' / 'mapa_locais.html'
    )
    builder.save()
