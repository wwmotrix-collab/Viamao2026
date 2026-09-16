"""
Pipeline de processamento de dados eleitorais.

Fluxo:
1. Leitura de dados brutos (CSV + XLSX)
2. Normalização e validação
3. Merge com coordenadas geográficas
4. Geração de agregações por local
5. Exportação em JSON normalizado
"""

import csv
import logging
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd
from utils import (
    DataProcessor, DataValidator, ReportGenerator,
    get_raw_dir, get_processed_dir
)

logger = logging.getLogger(__name__)


class SecaoProcessor:
    """Processador de dados de seções eleitorais."""
    
    def __init__(self):
        self.secoes_raw = []
        self.secoes_normalized = []
        self.relatorio = {}
    
    def carregar_csv(self, filepath: Path) -> bool:
        """Carrega arquivo CSV de seções."""
        try:
            df = pd.read_csv(filepath, encoding='utf-8')
            logger.info(f"Carregado: {filepath.name} ({len(df)} registros)")
            
            # Normalizar nomes de colunas
            df.columns = [col.lower().strip() for col in df.columns]
            
            self.secoes_raw = df.to_dict('records')
            return True
        except Exception as e:
            logger.error(f"Erro ao carregar {filepath}: {e}")
            return False
    
    def processar(self) -> Tuple[List[Dict], Dict]:
        """Processa seções e retorna dados normalizados."""
        
        self.secoes_normalized = []
        warnings = []
        erros = []
        
        for idx, sec in enumerate(self.secoes_raw):
            try:
                sec_norm = self._normalizar_secao(sec, idx)
                
                if sec_norm:
                    self.secoes_normalized.append(sec_norm)
                else:
                    erros.append(f"Seção {idx}: Falha na normalização")
                    
            except Exception as e:
                erros.append(f"Seção {idx}: {str(e)}")
                logger.warning(f"Erro ao processar seção {idx}: {e}")
        
        self.relatorio = ReportGenerator.gerar_relatorio_processamento(
            arquivo="tabela_detalhada_secoes_viamao.csv",
            total_registros=len(self.secoes_raw),
            registros_ok=len(self.secoes_normalized),
            warnings=warnings,
            erros=erros
        )
        
        logger.info(f"Processadas {len(self.secoes_normalized)}/{len(self.secoes_raw)} seções")
        return self.secoes_normalized, self.relatorio
    
    def _normalizar_secao(self, sec: Dict, idx: int) -> Dict:
        """Normaliza registro de seção."""
        
        # Extrair campos
        secao_num = int(sec.get('secao') or sec.get('numero_secao') or idx)
        votos_denise = int(sec.get('votos_denise') or sec.get('denise') or 0)
        votos_helenir = int(sec.get('votos_helenir') or sec.get('helenir') or 0)
        total = votos_denise + votos_helenir
        
        # Validar votos
        if not (DataValidator.validate_voto(votos_denise) and 
                DataValidator.validate_voto(votos_helenir)):
            return None
        
        # Calcular percentuais
        pct_denise = DataProcessor.calcular_percentual(votos_denise, total) if total > 0 else 0.0
        pct_helenir = DataProcessor.calcular_percentual(votos_helenir, total) if total > 0 else 0.0
        
        return {
            "secao_numero": secao_num,
            "zona_eleitoral": int(sec.get('zona_eleitoral') or sec.get('zona') or 0),
            "bairro": str(sec.get('bairro') or 'N/A').strip(),
            "local": str(sec.get('local') or sec.get('nome_local') or 'N/A').strip(),
            "endereco": str(sec.get('endereco') or 'N/A').strip(),
            "votos": {
                "denise": votos_denise,
                "helenir": votos_helenir,
                "total": total
            },
            "percentuais": {
                "denise": pct_denise,
                "helenir": pct_helenir
            },
            "abstencoes": None,
            "metadata": {
                "processado_em": pd.Timestamp.utcnow().isoformat() + "Z",
                "status": "OK"
            }
        }


class LocaisProcessor:
    """Processador de dados de locais de votação."""
    
    def __init__(self):
        self.locais_raw = []
        self.locais_normalized = []
        self.relatorio = {}
    
    def carregar_xlsx(self, filepath: Path) -> bool:
        """Carrega arquivo XLSX de locais."""
        try:
            df = pd.read_excel(filepath)
            logger.info(f"Carregado: {filepath.name} ({len(df)} registros)")
            
            # Normalizar nomes de colunas
            df.columns = [col.lower().strip() for col in df.columns]
            
            self.locais_raw = df.to_dict('records')
            return True
        except Exception as e:
            logger.error(f"Erro ao carregar {filepath}: {e}")
            return False
    
    def processar(self, secoes_normalized: List[Dict] = None) -> Tuple[List[Dict], Dict]:
        """Processa locais e retorna dados normalizados."""
        
        self.locais_normalized = []
        warnings = []
        erros = []
        
        # Criar mapa de seções por local
        secoes_por_local = {}
        if secoes_normalized:
            for sec in secoes_normalized:
                local_key = sec['local'].lower().strip()
                if local_key not in secoes_por_local:
                    secoes_por_local[local_key] = {
                        'votos_denise': 0,
                        'votos_helenir': 0,
                        'total_votos': 0,
                        'secoes': [],
                        'info': sec
                    }
                secoes_por_local[local_key]['votos_denise'] += sec['votos']['denise']
                secoes_por_local[local_key]['votos_helenir'] += sec['votos']['helenir']
                secoes_por_local[local_key]['total_votos'] += sec['votos']['total']
                secoes_por_local[local_key]['secoes'].append(sec['secao_numero'])
        
        for idx, local in enumerate(self.locais_raw):
            try:
                local_norm = self._normalizar_local(local, idx, secoes_por_local)
                
                if local_norm:
                    self.locais_normalized.append(local_norm)
                else:
                    warnings.append(f"Local {idx}: Falha na normalização")
                    
            except Exception as e:
                erros.append(f"Local {idx}: {str(e)}")
                logger.warning(f"Erro ao processar local {idx}: {e}")
        
        self.relatorio = ReportGenerator.gerar_relatorio_processamento(
            arquivo="locais_votacao.xlsx",
            total_registros=len(self.locais_raw),
            registros_ok=len(self.locais_normalized),
            warnings=warnings,
            erros=erros
        )
        
        logger.info(f"Processados {len(self.locais_normalized)}/{len(self.locais_raw)} locais")
        return self.locais_normalized, self.relatorio
    
    def _normalizar_local(self, local: Dict, idx: int, 
                          secoes_por_local: Dict = None) -> Dict:
        """Normaliza registro de local."""
        
        # Extrair coordenadas
        lat = float(local.get('latitude') or local.get('lat') or 0)
        lon = float(local.get('longitude') or local.get('lon') or 0)
        
        if not DataValidator.validate_coordenada(lat, lon):
            return None
        
        # Parse de seções
        secoes_str = str(local.get('secoes') or local.get('secao') or '')
        secoes = DataProcessor.parse_secoes_field(secoes_str)
        
        # Verificar se tem múltiplas seções (anomalia)
        anomalias = []
        if len(secoes) > 1:
            anomalias.append("multiplas_secoes_em_um_registro")
        
        # Buscar agregações
        agregado = {
            'votos_denise': 0,
            'votos_helenir': 0,
            'total_votos': 0,
            'num_secoes': len(secoes)
        }
        
        if secoes_por_local:
            local_key = str(local.get('local') or 'N/A').lower().strip()
            if local_key in secoes_por_local:
                agg = secoes_por_local[local_key]
                agregado['votos_denise'] = agg['votos_denise']
                agregado['votos_helenir'] = agg['votos_helenir']
                agregado['total_votos'] = agg['total_votos']
        
        # Calcular intensidade
        intensidade = 0.5
        if agregado['total_votos'] > 0:
            # Usar o máximo entre as candidatas
            max_votos = max(agregado['votos_denise'], agregado['votos_helenir'])
            intensidade = min(1.0, max_votos / (agregado['total_votos'] + 1))
        
        return {
            "id": f"loc_{idx:03d}",
            "nome": str(local.get('local') or 'N/A').strip(),
            "endereco": str(local.get('endereco') or 'N/A').strip(),
            "zona_eleitoral": int(local.get('zona') or 0),
            "bairro": str(local.get('bairro') or 'N/A').strip(),
            "coordenadas": {
                "latitude": lat,
                "longitude": lon
            },
            "secoes": sorted(secoes),
            "agregado": agregado,
            "marcador": {
                "tamanho": "medium",
                "intensidade": round(intensidade, 2),
                "cor": "#FF6B6B" if agregado['votos_denise'] > agregado['votos_helenir'] else "#4ECDC4"
            },
            "qualidade_dados": {
                "anomalias": anomalias,
                "status": "OK" if not anomalias else "WARNING"
            }
        }


class DataPipeline:
    """Pipeline de processamento completo."""
    
    def __init__(self, raw_dir: Path = None, processed_dir: Path = None):
        self.raw_dir = raw_dir or get_raw_dir()
        self.processed_dir = processed_dir or get_processed_dir()
        self.processed_dir.mkdir(parents=True, exist_ok=True)
    
    def executar(self) -> bool:
        """Executa pipeline completo."""
        
        logger.info("=" * 60)
        logger.info("Iniciando pipeline de processamento de dados")
        logger.info("=" * 60)
        
        try:
            # 1. Processar seções
            logger.info("\n[1/2] Processando seções...")
            sec_processor = SecaoProcessor()
            csv_path = self.raw_dir / 'tabela_detalhada_secoes_viamao.csv'
            
            if not sec_processor.carregar_csv(csv_path):
                logger.error("Falha ao carregar arquivo de seções")
                return False
            
            secoes_norm, sec_relatorio = sec_processor.processar()
            
            # Salvar seções
            DataProcessor.save_json(
                {"secoes": secoes_norm},
                self.processed_dir / 'secoes_normalized.json'
            )
            DataProcessor.save_json(
                sec_relatorio,
                self.processed_dir / 'relatorio_secoes.json'
            )
            
            # 2. Processar locais
            logger.info("\n[2/2] Processando locais...")
            loc_processor = LocaisProcessor()
            xlsx_path = self.raw_dir / 'locais_votacao (78).xlsx'
            
            if not loc_processor.carregar_xlsx(xlsx_path):
                logger.error("Falha ao carregar arquivo de locais")
                return False
            
            locais_norm, loc_relatorio = loc_processor.processar(secoes_norm)
            
            # Salvar locais
            DataProcessor.save_json(
                {"locais": locais_norm},
                self.processed_dir / 'locais_normalized.json'
            )
            DataProcessor.save_json(
                loc_relatorio,
                self.processed_dir / 'relatorio_locais.json'
            )
            
            # Relatório final
            logger.info("\n" + "=" * 60)
            logger.info("✓ Pipeline concluído com sucesso!")
            logger.info(f"  - {len(secoes_norm)} seções processadas")
            logger.info(f"  - {len(locais_norm)} locais processados")
            logger.info("=" * 60 + "\n")
            
            return True
            
        except Exception as e:
            logger.error(f"Erro no pipeline: {e}")
            return False


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    pipeline = DataPipeline()
    pipeline.executar()
