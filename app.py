# -*- coding: utf-8 -*-
"""
app.py - Aplicação Flask para Verificação de Elementos de Madeira (NBR 7190-1:2022)

Este módulo Flask implementa uma aplicação web para realizar cálculos e verificações
de dimensionamento de elementos estruturais de madeira, seguindo as diretrizes da
norma ABNT NBR 7190-1:2022.

Funcionalidades Principais:
- Apresenta um formulário para entrada de dados da peça de madeira e dos esforços.
- Valida os dados de entrada.
- Realiza cálculos geométricos e de propriedades da madeira.
- Efetua verificações de Estados Limites Últimos (ELU) e de Serviço (ELS).
- Exibe um relatório resumido e um relatório detalhado dos resultados.
"""

import math
import re
import traceback
import os # Adicionado para compatibilidade de deploy
from flask import Flask, render_template, request, url_for, session, redirect

# --- Importação SEGURA do Módulo de Cálculos ---
MODULO_CALCULOS_OK = False
tabelas_madeira = {}
kmod1_valores, kmod2_valores, TOL = {}, {}, 1e-9
GAMMA_M, GAMMA_C, GAMMA_T, GAMMA_V = 1.4, 1.4, 1.4, 1.8

try:
    from calculos_madeira import (
        tabelas_madeira, kmod1_valores, kmod2_valores,
        GAMMA_M, GAMMA_C, GAMMA_T, GAMMA_V, TOL,
        calcular_propriedades_geometricas, obter_propriedades_madeira,
        calcular_kmod, calcular_kmod1, calcular_kmod2,
        calcular_f_t0d, calcular_f_t90d, calcular_f_c0d,
        calcular_f_c90d, calcular_f_vd, calcular_f_md,
        obter_E0_med, obter_E0_05, obter_E0_ef,
        obter_G_med,
        verificar_dimensoes_minimas, verificar_tracao_simples,
        verificar_compressao_axial_com_estabilidade,
        verificar_flexocompressao_resistencia,
        verificar_flexocompressao_com_estabilidade,
        verificar_flexotracao,
        verificar_flexao_simples_reta,
        verificar_flexao_obliqua,
        verificar_cisalhamento,
        verificar_compressao_perpendicular,
        verificar_estabilidade_lateral_viga,
        calcular_flecha_instantanea_biapoiada_distribuida,
        obter_coeficiente_fluencia,
        verificar_flecha_final,
        verificar_flecha_instantanea_outra_comb
    )
    MODULO_CALCULOS_OK = True
    print("INFO: Módulo 'calculos_madeira.py' carregado com sucesso.")
except ImportError as e:
    MODULO_CALCULOS_OK = False
    print("*"*60); print(" ERRO CRÍTICO: Falha ao importar 'calculos_madeira.py'."); print(f" Detalhe: {e}"); print("*"*60)
except Exception as e_geral:
    MODULO_CALCULOS_OK = False
    print("*"*60); print(f" ERRO CRÍTICO INESPERADO durante a importação: {type(e_geral).__name__}"); print(f" Detalhe: {e_geral}"); print("*"*60)

app = Flask(__name__)

# --- Funções Auxiliares de Validação ---
def validar_float(valor_str, nome_campo, permitir_zero=True, permitir_negativo=True, minimo=None, maximo=None):
    """
    Valida e converte uma string para um número float.

    Args:
        valor_str (str): A string a ser validada e convertida.
        nome_campo (str): Nome do campo para mensagens de erro.
        permitir_zero (bool, optional): Se True, zero é um valor válido. Default é True.
        permitir_negativo (bool, optional): Se True, valores negativos são válidos. Default é True.
        minimo (float, optional): Valor mínimo permitido. Default é None.
        maximo (float, optional): Valor máximo permitido. Default é None.

    Returns:
        float: O valor convertido.

    Raises:
        ValueError: Se a validação falhar.
    """
    if valor_str is None or str(valor_str).strip() == "":
        if permitir_zero: return 0.0
        else: raise ValueError(f"Campo '{nome_campo}' é obrigatório e não pode ser zero.")
    try: valor_fmt = str(valor_str).strip().replace(',', '.')
    except AttributeError: raise ValueError(f"Entrada inválida para '{nome_campo}'. Esperado um número.")
    regex = r'^-?\d*\.?\d+$' if permitir_negativo else r'^\d*\.?\d+$'
    if not re.match(regex, valor_fmt): raise ValueError(f"Formato inválido para '{nome_campo}': '{valor_str}'.")
    try:
        valor = float(valor_fmt)
        if not permitir_zero and abs(valor) < TOL: raise ValueError(f"Campo '{nome_campo}' não pode ser zero.")
        if not permitir_negativo and valor < -TOL: raise ValueError(f"Campo '{nome_campo}' não pode ser negativo.")
        if minimo is not None and valor < minimo - TOL: raise ValueError(f"Campo '{nome_campo}' ({valor:.3f}) deve ser >= {minimo:.3f}.")
        if maximo is not None and valor > maximo + TOL: raise ValueError(f"Campo '{nome_campo}' ({valor:.3f}) deve ser <= {maximo:.3f}.")
        if nome_campo == 'alpha_n' and (valor < 1.0 - TOL or valor > 2.0 + TOL): raise ValueError(f"Campo '{nome_campo}' (αn) deve estar entre 1.0 e 2.0.")
        if nome_campo.startswith('Ke_') and valor < 0.5 - TOL: raise ValueError(f"Campo '{nome_campo}' (Ke) deve ser >= 0.5.")
        return valor
    except ValueError as e:
        if isinstance(e, ValueError) and e.args and isinstance(e.args[0], str) and any(term in e.args[0] for term in ["obrigatório", "deve estar entre", "deve ser >=", "não pode ser zero", "não pode ser negativo", "Formato inválido"]): raise e
        else: raise ValueError(f"Erro ao converter valor para '{nome_campo}': '{valor_str}'.") from e

def validar_selecao(valor_str, nome_campo, opcoes_validas=None):
    """
    Valida se uma string de seleção é obrigatória e se está entre as opções válidas.

    Args:
        valor_str (str): O valor da seleção.
        nome_campo (str): Nome do campo para mensagens de erro.
        opcoes_validas (list or dict, optional): Lista ou dicionário de opções válidas.
                                                  Se dict, as chaves são consideradas válidas.
                                                  Default é None (apenas verifica se não é vazio).
    Returns:
        str: O valor da seleção validado e 'stripado'.

    Raises:
        ValueError: Se a seleção for inválida ou obrigatória e estiver vazia.
    """
    if not valor_str or str(valor_str).strip() == "": raise ValueError(f"Seleção para '{nome_campo}' é obrigatória.")
    valor = str(valor_str).strip()
    if opcoes_validas is None: return valor
    opcoes_iteraveis = list(opcoes_validas.keys()) if isinstance(opcoes_validas, dict) else list(opcoes_validas) if hasattr(opcoes_validas, '__iter__') and not isinstance(opcoes_validas, str) else []
    if not opcoes_iteraveis: print(f"AVISO: Lista de opções válidas para '{nome_campo}' está vazia."); return valor
    if valor not in opcoes_iteraveis: op_str = ", ".join(map(str, opcoes_iteraveis)); raise ValueError(f"Valor '{valor}' inválido para '{nome_campo}'. Válidos: {op_str[:150] + '...' if len(op_str) > 150 else op_str}.")
    return valor

# --- Função Central de Cálculo ---
def realizar_calculo_completo(dados_validados):
    """
    Executa a sequência completa de cálculos e verificações da peça de madeira.

    Args:
        dados_validados (dict): Dicionário contendo todos os dados de entrada já validados.

    Returns:
        dict: Dicionário contendo os dados de entrada, os resultados dos cálculos
              intermediários e os resultados das verificações.

    Raises:
        ImportError: Se o módulo 'calculos_madeira' não estiver carregado.
        ValueError: Se ocorrer um erro durante os cálculos iniciais.
    """
    print("DEBUG: --- Iniciando realizar_calculo_completo ---")
    if not MODULO_CALCULOS_OK: raise ImportError("Módulo de cálculos não carregado.")
    resultados = dados_validados.copy(); resultados['calculos'] = {}; resultados['verificacoes'] = {}
    # A variável geral_ok será definida ao FINAL, baseada nas seleções do usuário.
    print(f"DEBUG: realizar_calculo_completo - verificacoes_selecionadas em dados_validados: {dados_validados.get('verificacoes_selecionadas')}")

    # --- Helper para formatar valores numéricos (ratios, termos, etc.) ---
    def formatar_valor_numerico(valor_num):
        """Formata um valor numérico para exibição, tratando infinito e NaN."""
        if isinstance(valor_num, (int, float)):
            if math.isinf(valor_num): return "Infinito"
            if math.isnan(valor_num): return "Indeterminado"
            return f"{valor_num:.3f}"
        return "N/A" # Se não for número (ex: None de um erro anterior ou cálculo não aplicável)

    try:
        # Cálculos iniciais de propriedades geométricas e da madeira
        largura = resultados['largura_mm']; altura = resultados['altura_mm']
        resultados['calculos']['k_M'] = 0.7 if abs(largura - altura) > TOL else 1.0 # Define k_M baseado na seção
        geom = calcular_propriedades_geometricas(largura, altura); resultados['calculos']['geom'] = geom; resultados['espessura_min_calculada'] = min(largura, altura)
        props_mad = obter_propriedades_madeira(resultados['tipo_tabela'], resultados['classe_madeira']); resultados['calculos']['props_mad'] = props_mad
        tipo_mad_kmod = "mlc" if resultados['tipo_madeira_beta_c'] == 'mlc' else "serrada"
        kmod1 = calcular_kmod1(resultados['classe_carregamento'], tipo_mad_kmod); kmod2 = calcular_kmod2(resultados['classe_umidade'], tipo_mad_kmod)
        k_mod = kmod1 * kmod2; resultados['calculos'].update({'kmod1': kmod1, 'kmod2': kmod2, 'k_mod': k_mod}); resultados['k_mod'] = k_mod
        f_keys = {k: props_mad.get(k) for k in ['f_t0k', 'f_t90k', 'f_c0k', 'f_c90k', 'f_vk', 'f_mk']}; resultados['calculos'].update(f_keys)
        f_t0d_calculado = calcular_f_t0d(f_keys['f_t0k'], k_mod); f_c0d_calculado = calcular_f_c0d(f_keys['f_c0k'], k_mod)
        f_d_values = {'f_t0d': f_t0d_calculado, 'f_c0d': f_c0d_calculado,
                      'f_t90d': calcular_f_t90d(f_keys['f_t90k'], f_t0d_calculado, k_mod),
                      'f_c90d': calcular_f_c90d(f_keys['f_c90k'], f_c0d_calculado, resultados.get('alpha_n', 1.0), k_mod),
                      'f_vd': calcular_f_vd(f_keys['f_vk'], k_mod),
                      'f_md': calcular_f_md(f_keys['f_mk'], f_c0d_calculado, k_mod, resultados['tipo_tabela'])}
        resultados['calculos'].update(f_d_values); resultados['calculos']['f_md_estimado'] = (resultados['tipo_tabela'] == 'nativa')
        E_vals = {'E_0med': obter_E0_med(props_mad), 'E_005': obter_E0_05(props_mad)}; E_vals['E_0ef'] = obter_E0_ef(props_mad, k_mod); E_vals['G_med'] = props_mad.get('G_med')
        resultados['calculos'].update(E_vals); resultados['calculos']['beta_c'] = 0.1 if resultados['tipo_madeira_beta_c'] == 'mlc' else 0.2; resultados['beta_c'] = resultados['calculos']['beta_c']
    except Exception as e: print(f"ERRO CRÍTICO cálculos iniciais: {e}"); traceback.print_exc(); raise ValueError(f"Falha cálculos iniciais: {e}") from e

    # Preparação dos esforços de cálculo ELU, aplicando excentricidade mínima se necessário
    Nsd_t0_calc = resultados['N_sd_t0_input']; Nsd_c0_calc = resultados['N_sd_c0_input']; Nsd_t90_calc = resultados['N_sd_t90_input']; Nsd_c90_calc = resultados['N_sd_c90_input']
    Vsd_calc_elu = abs(resultados['V_sd_input']); M_sdx_elu_orig = resultados['M_sd_x_Nm_input'] * 1000; M_sdy_elu_orig = resultados['M_sd_y_Nm_input'] * 1000
    resultados['calculos']['aplicou_exc_min'] = False; resultados['calculos']['e_min_mm'] = 0.0
    if Nsd_c0_calc > TOL and abs(M_sdx_elu_orig) <= TOL and abs(M_sdy_elu_orig) <= TOL: # Se apenas compressão axial
        e_min = resultados['comprimento_mm'] / (300.0 if resultados['tipo_madeira_beta_c'] == 'serrada' else 500.0) # Item 6.5.2 da NBR 7190
        M_sdx_elu_final = abs(Nsd_c0_calc * e_min); M_sdy_elu_final = abs(Nsd_c0_calc * e_min) # Aplica excentricidade mínima
        resultados['calculos'].update({'aplicou_exc_min': True, 'e_min_mm': e_min}); print(f"DEBUG: Excentricidade mínima aplicada. e_min={e_min:.2f}mm")
    else: M_sdx_elu_final = M_sdx_elu_orig; M_sdy_elu_final = M_sdy_elu_orig
    esforcos_calculo_elu = {'Nsd_t0': Nsd_t0_calc, 'Nsd_c0': Nsd_c0_calc, 'Nsd_t90': Nsd_t90_calc, 'Nsd_c90': Nsd_c90_calc, 'Vsd': Vsd_calc_elu, 'Msdx': M_sdx_elu_final, 'Msdy': M_sdy_elu_final}
    resultados['calculos']['esforcos_finais_elu'] = esforcos_calculo_elu; print(f"DEBUG: Esforços ELU finais: {esforcos_calculo_elu}")

    # Preparação dos esforços de cálculo ELS
    esforcos_calculo_els = {
        'q_qp_x': resultados.get('carga_els_qp_x', 0.0) / 1000.0, # N/m para N/mm
        'q_qp_y': resultados.get('carga_els_qp_y', 0.0) / 1000.0,
        'q_vento_x': resultados.get('carga_els_vento_x', 0.0) / 1000.0,
        'q_vento_y': resultados.get('carga_els_vento_y', 0.0) / 1000.0
    }
    resultados['calculos']['esforcos_finais_els_N_mm'] = esforcos_calculo_els; print(f"DEBUG: Esforços ELS (N/mm): {esforcos_calculo_els}")

    # Define aplicabilidade das verificações baseado nos esforços e seleções do usuário
    verificacao_flechas_selecionada = 'flechas_els' in resultados.get('verificacoes_selecionadas', [])
    is_tension_elu = esforcos_calculo_elu['Nsd_t0'] > TOL; is_compression_elu = esforcos_calculo_elu['Nsd_c0'] > TOL
    has_moment_x_elu = abs(esforcos_calculo_elu['Msdx']) > TOL; has_moment_y_elu = abs(esforcos_calculo_elu['Msdy']) > TOL
    has_moment_elu = has_moment_x_elu or has_moment_y_elu; has_shear_elu = esforcos_calculo_elu['Vsd'] > TOL
    has_perp_comp_elu = esforcos_calculo_elu['Nsd_c90'] > TOL; has_perp_tension_elu = esforcos_calculo_elu['Nsd_t90'] > TOL
    aplicabilidade = {
        'dimensoes': True,
        'tracao_simples': is_tension_elu,
        'tracao_perpendicular': has_perp_tension_elu,
        'compressao_simples_resistencia': is_compression_elu,
        'compressao_estabilidade': is_compression_elu, 
        'compressao_perpendicular': has_perp_comp_elu,
        'flexao_simples_reta': has_moment_elu and not is_tension_elu and not is_compression_elu and (has_moment_x_elu ^ has_moment_y_elu), 
        'flexao_obliqua': has_moment_x_elu and has_moment_y_elu and not is_tension_elu and not is_compression_elu,
        'flexotracao': is_tension_elu and has_moment_elu,
        'flexocompressao': is_compression_elu and has_moment_elu,
        'cisalhamento': has_shear_elu,
        'estabilidade_lateral': has_moment_x_elu, 
        'flechas_qp': verificacao_flechas_selecionada and (abs(esforcos_calculo_els['q_qp_x']) > TOL or abs(esforcos_calculo_els['q_qp_y']) > TOL),
        'flechas_vento': verificacao_flechas_selecionada and (abs(esforcos_calculo_els['q_vento_x']) > TOL or abs(esforcos_calculo_els['q_vento_y']) > TOL),
    }
    if resultados['calculos']['aplicou_exc_min']: 
        aplicabilidade['flexocompressao'] = True
        aplicabilidade['compressao_simples_resistencia'] = True 
        aplicabilidade['compressao_estabilidade'] = True
        aplicabilidade['flexao_simples_reta'] = False 
        aplicabilidade['flexao_obliqua'] = False

    print(f"DEBUG: realizar_calculo_completo - Aplicabilidade FINAL: {aplicabilidade}")

    # Inicializa o dicionário de verificações no objeto resultados
    chaves_todas = ['dimensoes', 'tracao_simples', 'tracao_perpendicular', 'compressao_simples_resistencia', 'compressao_estabilidade', 'compressao_perpendicular', 'flexao_simples_reta', 'flexao_obliqua', 'flexotracao', 'flexocompressao', 'cisalhamento', 'estabilidade_lateral', 'flechas_qp', 'flechas_vento']
    for chave in chaves_todas:
        resultados['verificacoes'][chave] = {
            'verificacao_aplicavel': aplicabilidade.get(chave, False),
            'passou': None, 'erro': None, 'is_combined_case': False,
            'esforcos': {}, 'ratio_formatado': 'N/A'
        }
    # Identifica casos combinados para evitar duplicidade de alertas de reprovação
    for chave in resultados['verificacoes']:
        if not resultados['verificacoes'][chave]['verificacao_aplicavel']:
            resultados['verificacoes'][chave]['is_combined_case'] = False 
            continue
        if chave == 'tracao_simples' and aplicabilidade.get('flexotracao', False):
            resultados['verificacoes'][chave]['is_combined_case'] = True
        if (chave == 'compressao_simples_resistencia' or chave == 'compressao_estabilidade') and aplicabilidade.get('flexocompressao', False):
            resultados['verificacoes'][chave]['is_combined_case'] = True
        if chave == 'flexao_simples_reta' and (aplicabilidade.get('flexao_obliqua', False) or aplicabilidade.get('flexotracao', False) or aplicabilidade.get('flexocompressao', False)):
            resultados['verificacoes'][chave]['is_combined_case'] = True

    # --- Execução das Verificações ---
    k_M_usar = resultados['calculos'].get('k_M', 0.7) 
    calc_data = resultados['calculos']
    geom = calc_data['geom']
    verifs = resultados['verificacoes'] 
    esforcos_elu = calc_data['esforcos_finais_elu']
    esforcos_els = calc_data['esforcos_finais_els_N_mm']

    # Bloco de verificações ELU
    if verifs['dimensoes']['verificacao_aplicavel']:
        try:
            a_ok, e_ok, a_req, e_req = verificar_dimensoes_minimas(resultados['largura_mm'], resultados['altura_mm'], resultados['tipo_peca_dim'])
            verifs['dimensoes'].update({'area_ok': a_ok, 'espessura_ok': e_ok, 'passou': a_ok and e_ok, 'area_req': a_req, 'espessura_req': e_req})
        except Exception as e: verifs['dimensoes'].update({'passou': False, 'erro': str(e)})

    if verifs['tracao_simples']['verificacao_aplicavel']:
        try:
            p, nsd, nrd, ratio_num = verificar_tracao_simples(esforcos_elu['Nsd_t0'], geom['area'], calc_data['f_t0d'])
            verifs['tracao_simples'].update({'passou': p, 'Nsd': nsd, 'NRd': nrd, 'Nsd_formatado': f"{nsd:.2f}", 'NRd_formatado': f"{nrd:.2f}", 'ratio': ratio_num, 'ratio_formatado': formatar_valor_numerico(ratio_num)})
        except Exception as e: verifs['tracao_simples'].update({'passou': False, 'erro': str(e), 'ratio_formatado': "Erro", 'Nsd_formatado': "Erro", 'NRd_formatado': "Erro"})

    if verifs['tracao_perpendicular']['verificacao_aplicavel']:
        try:
            p, nsd, nrd, ratio_num = verificar_compressao_perpendicular(esforcos_elu['Nsd_t90'], geom['area'], calc_data['f_t90d']) 
            verifs['tracao_perpendicular'].update({'passou': p, 'Nsd': nsd, 'NRd': nrd, 'Nsd_formatado': f"{nsd:.2f}", 'NRd_formatado': f"{nrd:.2f}", 'ratio': ratio_num, 'ratio_formatado': formatar_valor_numerico(ratio_num)})
        except Exception as e: verifs['tracao_perpendicular'].update({'passou': False, 'erro': str(e), 'ratio_formatado': "Erro", 'Nsd_formatado': "Erro", 'NRd_formatado': "Erro"})

    if verifs['compressao_simples_resistencia']['verificacao_aplicavel']:
        try:
            res_comp = verificar_compressao_axial_com_estabilidade(esforcos_elu['Nsd_c0'], geom['area'], calc_data['f_c0k'], calc_data['f_c0d'], calc_data['E_005'], resultados['comprimento_mm'], resultados['Ke_x'], resultados['Ke_y'], props_geom=geom, beta_c=calc_data['beta_c'])
            nsd_comp, NRd_res_comp, NRd_est_comp = res_comp[1], res_comp[3], res_comp[5]
            ratio_res_comp_num = nsd_comp / NRd_res_comp if abs(NRd_res_comp) > TOL else (0.0 if abs(nsd_comp) < TOL else float('inf'))
            ratio_est_comp_num = nsd_comp / NRd_est_comp if abs(NRd_est_comp) > TOL else (0.0 if abs(nsd_comp) < TOL else float('inf'))

            verifs['compressao_simples_resistencia'].update({'passou': res_comp[2], 'Nsd': nsd_comp, 'NRd': NRd_res_comp, 'Nsd_formatado': f"{nsd_comp:.2f}", 'NRd_res_formatado': f"{NRd_res_comp:.2f}", 'ratio': ratio_res_comp_num, 'ratio_formatado': formatar_valor_numerico(ratio_res_comp_num), 'passou_geral_compressao_pura': res_comp[0]})
            verifs['compressao_estabilidade'].update({
                'verificacao_aplicavel': True, 
                'passou': res_comp[4], 'Nsd': nsd_comp, 'NRd': NRd_est_comp, 'Nsd_formatado': f"{nsd_comp:.2f}", 'NRd_est_formatado': f"{NRd_est_comp:.2f}",
                'lambda_x': res_comp[6], 'lambda_y': res_comp[7], 'lambda_rel_x': res_comp[8], 'lambda_rel_y': res_comp[9],
                'kc_x': res_comp[10], 'kc_y': res_comp[11], 'esbeltez_ok': res_comp[12], 'lambda_max': max(res_comp[6],res_comp[7]),
                'kc_min': min(res_comp[10],res_comp[11]), 'passou_est_apenas':res_comp[13], 'ratio': ratio_est_comp_num, 'ratio_formatado': formatar_valor_numerico(ratio_est_comp_num)
            })
        except Exception as e:
            verifs['compressao_simples_resistencia'].update({'passou': False, 'erro': str(e), 'ratio_formatado': "Erro"});
            verifs['compressao_estabilidade'].update({'passou': False, 'erro': str(e), 'ratio_formatado': "Erro"});

    if verifs['compressao_perpendicular']['verificacao_aplicavel']:
        try:
            area_apoio_compressao_perp = geom['area'] 
            p, nsd, nrd, ratio_num = verificar_compressao_perpendicular(esforcos_elu['Nsd_c90'], area_apoio_compressao_perp, calc_data['f_c90d'])
            verifs['compressao_perpendicular'].update({'passou': p, 'Nsd': nsd, 'NRd': nrd, 'Nsd_formatado': f"{nsd:.2f}", 'NRd_formatado': f"{nrd:.2f}",'Area_apoio_usada': area_apoio_compressao_perp, 'ratio': ratio_num, 'ratio_formatado': formatar_valor_numerico(ratio_num)})
        except Exception as e: verifs['compressao_perpendicular'].update({'passou': False, 'erro': str(e), 'ratio_formatado': "Erro", 'Nsd_formatado': "Erro", 'NRd_formatado': "Erro"})

    if verifs['flexao_simples_reta']['verificacao_aplicavel']:
        passou_flex_x, passou_flex_y = True, True
        erro_flex_x, erro_flex_y = None, None
        verifs['flexao_simples_reta']['x'] = {'verificacao_aplicavel': False, 'passou': True, 'ratio_formatado': 'N/A', 'Msd_formatado': 'N/A', 'MRd_formatado': 'N/A'}
        verifs['flexao_simples_reta']['y'] = {'verificacao_aplicavel': False, 'passou': True, 'ratio_formatado': 'N/A', 'Msd_formatado': 'N/A', 'MRd_formatado': 'N/A'}

        if abs(esforcos_elu['Msdx']) > TOL: 
            verifs['flexao_simples_reta']['x']['verificacao_aplicavel'] = True
            try:
                px, msdx, mrx, ratio_x_num = verificar_flexao_simples_reta(esforcos_elu['Msdx'], geom['W_x'], calc_data['f_md'])
                verifs['flexao_simples_reta']['x'].update({'passou': px, 'Msd': msdx, 'MRd': mrx, 'Msd_formatado': f"{msdx:.2f}", 'MRd_formatado': f"{mrx:.2f}", 'ratio': ratio_x_num, 'ratio_formatado': formatar_valor_numerico(ratio_x_num)})
                if not px: passou_flex_x = False
            except Exception as e: erro_flex_x = str(e); passou_flex_x = False; verifs['flexao_simples_reta']['x'].update({'passou': False, 'erro': erro_flex_x, 'ratio_formatado': "Erro"})

        if abs(esforcos_elu['Msdy']) > TOL: 
            verifs['flexao_simples_reta']['y']['verificacao_aplicavel'] = True
            try:
                 py, msdy, mry, ratio_y_num = verificar_flexao_simples_reta(esforcos_elu['Msdy'], geom['W_y'], calc_data['f_md'])
                 verifs['flexao_simples_reta']['y'].update({'passou': py, 'Msd': msdy, 'MRd': mry, 'Msd_formatado': f"{msdy:.2f}", 'MRd_formatado': f"{mry:.2f}", 'ratio': ratio_y_num, 'ratio_formatado': formatar_valor_numerico(ratio_y_num)})
                 if not py: passou_flex_y = False
            except Exception as e: erro_flex_y = str(e); passou_flex_y = False; verifs['flexao_simples_reta']['y'].update({'passou': False, 'erro': erro_flex_y, 'ratio_formatado': "Erro"})

        passou_fsr_total = passou_flex_x and passou_flex_y
        if verifs['flexao_simples_reta']['x']['verificacao_aplicavel'] or verifs['flexao_simples_reta']['y']['verificacao_aplicavel']:
            verifs['flexao_simples_reta']['passou'] = passou_fsr_total 
            if erro_flex_x or erro_flex_y: verifs['flexao_simples_reta']['erro'] = f"X:{erro_flex_x or '-'} | Y:{erro_flex_y or '-'}"
        else: 
             verifs['flexao_simples_reta']['verificacao_aplicavel'] = False
             verifs['flexao_simples_reta']['passou'] = True 

    if verifs['flexao_obliqua']['verificacao_aplicavel']:
        try:
            p, ratio_num_fo = verificar_flexao_obliqua(esforcos_elu['Msdx'], esforcos_elu['Msdy'], geom['W_x'], geom['W_y'], calc_data['f_md'], k_M=k_M_usar)
            termo_Mx_num = abs(esforcos_elu['Msdx']) / (calc_data['f_md'] * geom['W_x']) if abs(calc_data['f_md'] * geom['W_x']) > TOL else (0.0 if abs(esforcos_elu['Msdx']) < TOL else float('inf'))
            termo_My_num = abs(esforcos_elu['Msdy']) / (calc_data['f_md'] * geom['W_y']) if abs(calc_data['f_md'] * geom['W_y']) > TOL else (0.0 if abs(esforcos_elu['Msdy']) < TOL else float('inf'))
            ratio1_fo_num = termo_Mx_num + k_M_usar * termo_My_num if isinstance(termo_Mx_num, float) and isinstance(termo_My_num, float) and not (math.isinf(termo_Mx_num) or math.isinf(termo_My_num) or math.isnan(termo_Mx_num) or math.isnan(termo_My_num)) else float('inf')
            ratio2_fo_num = k_M_usar * termo_Mx_num + termo_My_num if isinstance(termo_Mx_num, float) and isinstance(termo_My_num, float) and not (math.isinf(termo_Mx_num) or math.isinf(termo_My_num) or math.isnan(termo_Mx_num) or math.isnan(termo_My_num)) else float('inf')

            verifs['flexao_obliqua'].update({
                'passou': p, 'ratio': ratio_num_fo, 'ratio_formatado': formatar_valor_numerico(ratio_num_fo),
                'Msdx': esforcos_elu['Msdx'], 'Msdy': esforcos_elu['Msdy'], 'k_M_usado': k_M_usar,
                'termo_Mx_formatado': formatar_valor_numerico(termo_Mx_num),
                'termo_My_formatado': formatar_valor_numerico(termo_My_num),
                'ratio1_fo_formatado': formatar_valor_numerico(ratio1_fo_num),
                'ratio2_fo_formatado': formatar_valor_numerico(ratio2_fo_num)
            })
        except Exception as e: verifs['flexao_obliqua'].update({'passou': False, 'erro': str(e), 'ratio_formatado': "Erro", 'termo_Mx_formatado': "Erro", 'termo_My_formatado': "Erro", 'ratio1_fo_formatado': "Erro", 'ratio2_fo_formatado': "Erro"})

    if verifs['flexotracao']['verificacao_aplicavel']:
        try:
            p, ratio_num_ft = verificar_flexotracao(esforcos_elu['Nsd_t0'], esforcos_elu['Msdx'], esforcos_elu['Msdy'], geom['area'], geom['W_x'], geom['W_y'], calc_data['f_t0d'], calc_data['f_md'], k_M=k_M_usar)
            termo_N_num = esforcos_elu['Nsd_t0'] / (calc_data['f_t0d'] * geom['area']) if abs(calc_data['f_t0d'] * geom['area']) > TOL else (0.0 if abs(esforcos_elu['Nsd_t0']) < TOL else float('inf'))
            termo_Mx_num = abs(esforcos_elu['Msdx']) / (calc_data['f_md'] * geom['W_x']) if abs(calc_data['f_md'] * geom['W_x']) > TOL else (0.0 if abs(esforcos_elu['Msdx']) < TOL else float('inf'))
            termo_My_num = abs(esforcos_elu['Msdy']) / (calc_data['f_md'] * geom['W_y']) if abs(calc_data['f_md'] * geom['W_y']) > TOL else (0.0 if abs(esforcos_elu['Msdy']) < TOL else float('inf'))
            ratio1_ft_num = float('inf'); ratio2_ft_num = float('inf')
            if not any(math.isinf(x) or math.isnan(x) for x in [termo_N_num, termo_Mx_num, termo_My_num]): 
                 ratio1_ft_num = termo_N_num + termo_Mx_num + k_M_usar * termo_My_num
                 ratio2_ft_num = termo_N_num + k_M_usar * termo_Mx_num + termo_My_num

            verifs['flexotracao'].update({
                'passou': p, 'ratio': ratio_num_ft, 'ratio_formatado': formatar_valor_numerico(ratio_num_ft),
                'Nsd': esforcos_elu['Nsd_t0'], 'Msdx': esforcos_elu['Msdx'], 'Msdy': esforcos_elu['Msdy'], 'k_M_usado': k_M_usar,
                'termo_N_formatado': formatar_valor_numerico(termo_N_num),
                'termo_Mx_formatado': formatar_valor_numerico(termo_Mx_num),
                'termo_My_formatado': formatar_valor_numerico(termo_My_num),
                'ratio1_ft_formatado': formatar_valor_numerico(ratio1_ft_num),
                'ratio2_ft_formatado': formatar_valor_numerico(ratio2_ft_num)
            })
        except Exception as e: verifs['flexotracao'].update({'passou': False, 'erro': str(e), 'ratio_formatado': "Erro", 'termo_N_formatado': "Erro", 'termo_Mx_formatado': "Erro", 'termo_My_formatado': "Erro", 'ratio1_ft_formatado': "Erro", 'ratio2_ft_formatado': "Erro"})

    if verifs['flexocompressao']['verificacao_aplicavel']:
        passou_fc_res, passou_fc_est_final = True, True 
        erro_fc_res, erro_fc_est = None, None
        verifs['flexocompressao']['resistencia'] = {'passou': False, 'ratio_formatado': 'N/A', 'termo_N_quad_formatado': 'N/A', 'termo_Mx_fmd_formatado': 'N/A', 'termo_My_fmd_formatado': 'N/A', 'ratio1_fc_res_formatado': 'N/A', 'ratio2_fc_res_formatado': 'N/A'}
        verifs['flexocompressao']['estabilidade'] = {'passou': False, 'ratio_formatado': 'N/A', 'termo_N_kcx_formatado': 'N/A', 'termo_N_kcy_formatado': 'N/A', 'termo_Mx_fmd_formatado': 'N/A', 'termo_My_fmd_formatado': 'N/A', 'ratio1_fc_est_formatado': 'N/A', 'ratio2_fc_est_formatado': 'N/A'}
        try: 
            p_res, ratio_res_fc_num = verificar_flexocompressao_resistencia(esforcos_elu['Nsd_c0'], esforcos_elu['Msdx'], esforcos_elu['Msdy'], geom['area'], geom['W_x'], geom['W_y'], calc_data['f_c0d'], calc_data['f_md'], k_M=k_M_usar)
            sigma_Ncd_val = abs(esforcos_elu['Nsd_c0']) / geom['area'] if geom['area'] > TOL else float('inf')
            sigma_Msdx_val = abs(esforcos_elu['Msdx']) / geom['W_x'] if geom['W_x'] > TOL else float('inf')
            sigma_Msdy_val = abs(esforcos_elu['Msdy']) / geom['W_y'] if geom['W_y'] > TOL else float('inf')
            termo_N_quad_num = (sigma_Ncd_val / calc_data['f_c0d'])**2 if abs(calc_data['f_c0d']) > TOL else float('inf')
            termo_Mx_fmd_num_res = sigma_Msdx_val / calc_data['f_md'] if abs(calc_data['f_md']) > TOL else float('inf')
            termo_My_fmd_num_res = sigma_Msdy_val / calc_data['f_md'] if abs(calc_data['f_md']) > TOL else float('inf')
            ratio1_fc_res_num, ratio2_fc_res_num = float('inf'), float('inf')
            if not any(math.isinf(x) or math.isnan(x) for x in [termo_N_quad_num, termo_Mx_fmd_num_res, termo_My_fmd_num_res]):
                ratio1_fc_res_num = termo_N_quad_num + termo_Mx_fmd_num_res + k_M_usar * termo_My_fmd_num_res
                ratio2_fc_res_num = termo_N_quad_num + k_M_usar * termo_Mx_fmd_num_res + termo_My_fmd_num_res

            verifs['flexocompressao']['resistencia'].update({'passou': p_res, 'ratio': ratio_res_fc_num, 'ratio_formatado': formatar_valor_numerico(ratio_res_fc_num), 'Nsd': esforcos_elu['Nsd_c0'], 'Msdx': esforcos_elu['Msdx'], 'Msdy': esforcos_elu['Msdy'], 'k_M_usado': k_M_usar, 'termo_N_quad_formatado': formatar_valor_numerico(termo_N_quad_num), 'termo_Mx_fmd_formatado': formatar_valor_numerico(termo_Mx_fmd_num_res), 'termo_My_fmd_formatado': formatar_valor_numerico(termo_My_fmd_num_res), 'ratio1_fc_res_formatado': formatar_valor_numerico(ratio1_fc_res_num), 'ratio2_fc_res_formatado': formatar_valor_numerico(ratio2_fc_res_num)})
            if not p_res: passou_fc_res = False
        except Exception as e: erro_fc_res = str(e); passou_fc_res = False; verifs['flexocompressao']['resistencia'].update({'passou': False, 'erro': erro_fc_res, 'ratio_formatado': "Erro"})

        try: 
            res_fc_est = verificar_flexocompressao_com_estabilidade(esforcos_elu['Nsd_c0'], esforcos_elu['Msdx'], esforcos_elu['Msdy'], geom['area'], geom['W_x'], geom['W_y'], calc_data['f_c0k'], calc_data['f_c0d'], calc_data['f_md'], calc_data['E_005'], resultados['comprimento_mm'], resultados['Ke_x'], resultados['Ke_y'], props_geom=geom, beta_c=calc_data['beta_c'], k_M=k_M_usar)
            sigma_Ncd_val_est = abs(esforcos_elu['Nsd_c0']) / geom['area'] if geom['area'] > TOL else float('inf')
            kc_x_val, kc_y_val = res_fc_est[6], res_fc_est[7] 
            termo_N_kcx_num = sigma_Ncd_val_est / (kc_x_val * calc_data['f_c0d']) if abs(kc_x_val * calc_data['f_c0d']) > TOL else float('inf')
            termo_N_kcy_num = sigma_Ncd_val_est / (kc_y_val * calc_data['f_c0d']) if abs(kc_y_val * calc_data['f_c0d']) > TOL else float('inf')
            termo_Mx_fmd_num_est = abs(esforcos_elu['Msdx']) / (calc_data['f_md'] * geom['W_x']) if abs(calc_data['f_md'] * geom['W_x']) > TOL else float('inf')
            termo_My_fmd_num_est = abs(esforcos_elu['Msdy']) / (calc_data['f_md'] * geom['W_y']) if abs(calc_data['f_md'] * geom['W_y']) > TOL else float('inf')
            ratio1_fc_est_num, ratio2_fc_est_num = float('inf'), float('inf')
            if not any(math.isinf(x) or math.isnan(x) for x in [termo_N_kcx_num, termo_Mx_fmd_num_est, termo_My_fmd_num_est]):
                 ratio1_fc_est_num = termo_N_kcx_num + termo_Mx_fmd_num_est + k_M_usar * termo_My_fmd_num_est
            if not any(math.isinf(x) or math.isnan(x) for x in [termo_N_kcy_num, termo_Mx_fmd_num_est, termo_My_fmd_num_est]):
                 ratio2_fc_est_num = termo_N_kcy_num + k_M_usar * termo_Mx_fmd_num_est + termo_My_fmd_num_est

            verifs['flexocompressao']['estabilidade'].update({'passou': res_fc_est[0], 'ratio': res_fc_est[1], 'ratio_formatado': formatar_valor_numerico(res_fc_est[1]), 'lambda_x': res_fc_est[2], 'lambda_y': res_fc_est[3], 'lambda_rel_x': res_fc_est[4], 'lambda_rel_y': res_fc_est[5], 'kc_x': kc_x_val, 'kc_y': kc_y_val, 'k_M_usado': k_M_usar, 'lambda_max': res_fc_est[8], 'esbeltez_ok': res_fc_est[9], 'passou_ratio_apenas': res_fc_est[10], 'termo_N_kcx_formatado': formatar_valor_numerico(termo_N_kcx_num), 'termo_N_kcy_formatado': formatar_valor_numerico(termo_N_kcy_num), 'termo_Mx_fmd_formatado': formatar_valor_numerico(termo_Mx_fmd_num_est), 'termo_My_fmd_formatado': formatar_valor_numerico(termo_My_fmd_num_est), 'ratio1_fc_est_formatado': formatar_valor_numerico(ratio1_fc_est_num), 'ratio2_fc_est_formatado': formatar_valor_numerico(ratio2_fc_est_num)})
            if not res_fc_est[0]: passou_fc_est_final = False
        except Exception as e: erro_fc_est = str(e); passou_fc_est_final = False; verifs['flexocompressao']['estabilidade'].update({'passou': False, 'erro': erro_fc_est, 'ratio_formatado': "Erro"})

        passou_fc_total = passou_fc_res and passou_fc_est_final
        verifs['flexocompressao']['passou'] = passou_fc_total 
        if erro_fc_res or erro_fc_est: verifs['flexocompressao']['erro'] = f"Res:{erro_fc_res or '-'} | Est:{erro_fc_est or '-'}"

    if verifs['cisalhamento']['verificacao_aplicavel']:
        try:
            p, vsd, vrd, ratio_num = verificar_cisalhamento(esforcos_elu['Vsd'], geom['area'], calc_data['f_vd'])
            verifs['cisalhamento'].update({'passou': p, 'Vsd': vsd, 'VRd': vrd, 'Vsd_formatado': f"{vsd:.2f}", 'VRd_formatado': f"{vrd:.2f}", 'ratio': ratio_num, 'ratio_formatado': formatar_valor_numerico(ratio_num)})
        except Exception as e: verifs['cisalhamento'].update({'passou': False, 'erro': str(e), 'ratio_formatado': "Erro"})

    if verifs['estabilidade_lateral']['verificacao_aplicavel']:
        try:
            resultados_fl = verificar_estabilidade_lateral_viga(resultados['largura_mm'], resultados['altura_mm'], resultados['L1_mm'], calc_data['E_0med'], calc_data['f_md'], calc_data['k_mod'], esforcos_elu['Msdx'], geom['W_x'])
            ratio_fl_num = float('nan') 
            sigma_cd_atuante_num = resultados_fl.get('sigma_cd_atuante')
            sigma_cd_max_adm_num = resultados_fl.get('sigma_cd_max_adm')
            resultados_fl['sigma_cd_atuante_formatado'] = formatar_valor_numerico(sigma_cd_atuante_num) if isinstance(sigma_cd_atuante_num, (int,float)) else "N/A"
            resultados_fl['sigma_cd_max_adm_formatado'] = formatar_valor_numerico(sigma_cd_max_adm_num) if isinstance(sigma_cd_max_adm_num, (int,float)) else "N/A"

            if not resultados_fl.get('dispensado') and isinstance(sigma_cd_atuante_num, (int,float)) and isinstance(sigma_cd_max_adm_num, (int,float)) and abs(sigma_cd_max_adm_num) > TOL:
                ratio_fl_num = sigma_cd_atuante_num / sigma_cd_max_adm_num
            elif not resultados_fl.get('dispensado'): 
                ratio_fl_num = float('inf') if isinstance(sigma_cd_atuante_num, (int,float)) and abs(sigma_cd_atuante_num) > TOL else (0.0 if isinstance(sigma_cd_atuante_num, (int,float)) else float('nan'))
            resultados_fl['ratio_formatado'] = formatar_valor_numerico(ratio_fl_num) if not resultados_fl.get('dispensado') else "Dispensado"

            verifs['estabilidade_lateral'].update(resultados_fl)
            if resultados_fl.get('erro'):
                verifs['estabilidade_lateral']['passou'] = False 
        except Exception as e: verifs['estabilidade_lateral'].update({'passou': False, 'erro': str(e), 'ratio_formatado': "Erro"})

    # Bloco de verificações ELS (Flechas)
    passou_els_geral_para_calculo_interno = True # Nova flag para status interno do ELS
    if verificacao_flechas_selecionada:
        l_mm = resultados['comprimento_mm']
        e0_para_flecha = calc_data.get('E_0med')
        phi = calc_data.get('phi') 

        if phi is None: 
            try:
                phi = obter_coeficiente_fluencia(resultados['classe_umidade'], tipo_mad_kmod) 
                calc_data['phi'] = phi 
            except Exception as e:
                 if verifs['flechas_qp']['verificacao_aplicavel']: verifs['flechas_qp'].update({'passou': False, 'erro': f"Erro ao obter phi: {e}", 'ratio_formatado': "Erro"})
                 if verifs['flechas_vento']['verificacao_aplicavel']: verifs['flechas_vento'].update({'passou': False, 'erro': f"Erro ao obter phi: {e}", 'ratio_formatado': "Erro"})
                 phi = None 
                 passou_els_geral_para_calculo_interno = False

        if verifs['flechas_qp']['verificacao_aplicavel'] and phi is not None:
            try:
                delta_inst_qp_x = calcular_flecha_instantanea_biapoiada_distribuida(q=esforcos_els['q_qp_x'], L=l_mm, E0_med=e0_para_flecha, I=geom['I_y'])
                delta_inst_qp_y = calcular_flecha_instantanea_biapoiada_distribuida(q=esforcos_els['q_qp_y'], L=l_mm, E0_med=e0_para_flecha, I=geom['I_x'])
                passou_qp, d_x_fin, d_y_fin, d_res, d_lim = verificar_flecha_final(delta_inst_qp_x, delta_inst_qp_y, phi, l_mm, tipo_viga='biapoiada')
                ratio_qp_str = "N/A"
                if abs(d_lim) > TOL: ratio_val = d_res / d_lim; ratio_qp_str = formatar_valor_numerico(ratio_val)
                elif abs(d_res) <= TOL: ratio_qp_str = "0.000" 
                else: ratio_qp_str = "Infinito" 
                verifs['flechas_qp'].update({'passou': passou_qp, 'delta_inst_x': delta_inst_qp_x, 'delta_inst_y': delta_inst_qp_y, 'phi': phi, 'delta_x_final': d_x_fin, 'delta_y_final': d_y_fin, 'delta_resultante': d_res, 'delta_limite': d_lim, 'ratio_formatado': ratio_qp_str})
                if not passou_qp: passou_els_geral_para_calculo_interno = False
            except Exception as e: verifs['flechas_qp'].update({'passou': False, 'erro': str(e), 'ratio_formatado': "Erro"}); passou_els_geral_para_calculo_interno = False
        elif phi is None and verifs['flechas_qp']['verificacao_aplicavel']: 
             verifs['flechas_qp'].update({'passou': False, 'erro': "Coeficiente de fluência (phi) não pôde ser determinado.", 'ratio_formatado': "Erro"})
             passou_els_geral_para_calculo_interno = False

        if verifs['flechas_vento']['verificacao_aplicavel'] and phi is not None: 
            try:
                delta_inst_vento_x = calcular_flecha_instantanea_biapoiada_distribuida(q=esforcos_els['q_vento_x'], L=l_mm, E0_med=e0_para_flecha, I=geom['I_y'])
                delta_inst_vento_y = calcular_flecha_instantanea_biapoiada_distribuida(q=esforcos_els['q_vento_y'], L=l_mm, E0_med=e0_para_flecha, I=geom['I_x'])
                passou_vento, d_x_fin_v, d_y_fin_v, d_res_v, d_lim_v = verificar_flecha_final(delta_inst_vento_x, delta_inst_vento_y, phi, l_mm, tipo_viga='biapoiada')
                ratio_vento_str = "N/A"
                if abs(d_lim_v) > TOL: ratio_val_v = abs(d_res_v) / d_lim_v; ratio_vento_str = formatar_valor_numerico(ratio_val_v) 
                elif abs(d_res_v) <= TOL: ratio_vento_str = "0.000"
                else: ratio_vento_str = "Infinito"
                verifs['flechas_vento'].update({'passou': passou_vento, 'delta_inst_x': delta_inst_vento_x, 'delta_inst_y': delta_inst_vento_y, 'phi': phi, 'delta_x_final': d_x_fin_v, 'delta_y_final': d_y_fin_v, 'delta_resultante': d_res_v, 'delta_limite': d_lim_v, 'ratio_formatado': ratio_vento_str})
                if not passou_vento: passou_els_geral_para_calculo_interno = False
            except Exception as e: verifs['flechas_vento'].update({'passou': False, 'erro': str(e), 'ratio_formatado': "Erro"}); passou_els_geral_para_calculo_interno = False
        elif phi is None and verifs['flechas_vento']['verificacao_aplicavel']:
             verifs['flechas_vento'].update({'passou': False, 'erro': "Coeficiente de fluência (phi) não pôde ser determinado.", 'ratio_formatado': "Erro"})
             passou_els_geral_para_calculo_interno = False


    # --- NOVO BLOCO PARA RECALCULAR geral_ok COM BASE NAS SELEÇÕES DO USUÁRIO ---
    geral_ok_final = True # Assume aprovado inicialmente
    verificacoes_selecionadas_pelo_usuario = resultados.get('verificacoes_selecionadas', [])
    verificacoes_processadas = resultados['verificacoes']

    print(f"DEBUG: Recalculando geral_ok. Selecionadas pelo usuário: {verificacoes_selecionadas_pelo_usuario}")

    for chave_form_selecionada in verificacoes_selecionadas_pelo_usuario:
        verificacao_com_falha_ou_erro_para_item_selecionado = False

        if chave_form_selecionada == 'dimensoes':
            v = verificacoes_processadas.get('dimensoes', {})
            if v.get('verificacao_aplicavel') and (v.get('erro') or v.get('passou') is False):
                verificacao_com_falha_ou_erro_para_item_selecionado = True
        
        elif chave_form_selecionada == 'tracao_simples':
            v = verificacoes_processadas.get('tracao_simples', {})
            if v.get('verificacao_aplicavel') and (v.get('erro') or v.get('passou') is False):
                # Considera falha se não for um caso combinado que será coberto por um "pai" também selecionado.
                # Se 'flexotracao' não estiver selecionada, a falha de 'tracao_simples' conta.
                if not v.get('is_combined_case') or 'flexotracao' not in verificacoes_selecionadas_pelo_usuario:
                    verificacao_com_falha_ou_erro_para_item_selecionado = True
        
        elif chave_form_selecionada == 'compressao_simples_resistencia': 
            v_res = verificacoes_processadas.get('compressao_simples_resistencia', {})
            v_est = verificacoes_processadas.get('compressao_estabilidade', {})
            if v_res.get('verificacao_aplicavel'):
                if v_res.get('erro') or v_est.get('erro'):
                    verificacao_com_falha_ou_erro_para_item_selecionado = True
                elif v_res.get('passou_geral_compressao_pura') is False:
                    if not v_res.get('is_combined_case') or 'flexocompressao' not in verificacoes_selecionadas_pelo_usuario:
                        verificacao_com_falha_ou_erro_para_item_selecionado = True
                        
        elif chave_form_selecionada == 'flexao_simples_reta':
            v = verificacoes_processadas.get('flexao_simples_reta', {})
            if v.get('verificacao_aplicavel') and (v.get('erro') or v.get('passou') is False):
                is_combined = v.get('is_combined_case', False)
                # Verifica se algum dos "pais" que tornariam este 'is_combined' foi selecionado
                parent_selected = False
                if 'flexao_obliqua' in verificacoes_selecionadas_pelo_usuario and resultados['verificacoes'].get('flexao_obliqua',{}).get('verificacao_aplicavel'):
                    parent_selected = True
                if not parent_selected and 'flexotracao' in verificacoes_selecionadas_pelo_usuario and resultados['verificacoes'].get('flexotracao',{}).get('verificacao_aplicavel'):
                    parent_selected = True
                if not parent_selected and 'flexocompressao' in verificacoes_selecionadas_pelo_usuario and resultados['verificacoes'].get('flexocompressao',{}).get('verificacao_aplicavel'):
                    parent_selected = True
                
                if not is_combined or not parent_selected: # Se não é combinado, ou se é mas o pai não foi selecionado
                     verificacao_com_falha_ou_erro_para_item_selecionado = True

        elif chave_form_selecionada == 'flechas_els': 
            v_qp = verificacoes_processadas.get('flechas_qp', {})
            v_vento = verificacoes_processadas.get('flechas_vento', {})
            aplic_qp = v_qp.get('verificacao_aplicavel', False)
            aplic_vento = v_vento.get('verificacao_aplicavel', False)
            if aplic_qp or aplic_vento : 
                if v_qp.get('erro') or v_vento.get('erro'):
                    verificacao_com_falha_ou_erro_para_item_selecionado = True
                else:
                    passou_qp_final = (not aplic_qp) or (v_qp.get('passou') is True)
                    passou_vento_final = (not aplic_vento) or (v_vento.get('passou') is True)
                    if not (passou_qp_final and passou_vento_final):
                        verificacao_com_falha_ou_erro_para_item_selecionado = True
        
        elif chave_form_selecionada == 'estabilidade_lateral':
            v = verificacoes_processadas.get('estabilidade_lateral',{})
            if v.get('verificacao_aplicavel'):
                if v.get('erro'):
                    verificacao_com_falha_ou_erro_para_item_selecionado = True
                elif not v.get('dispensado', False) and v.get('passou') is False:
                    verificacao_com_falha_ou_erro_para_item_selecionado = True
        
        elif chave_form_selecionada in ['tracao_perpendicular', 'compressao_perpendicular', 
                                       'flexao_obliqua', 'flexotracao', 'flexocompressao', 'cisalhamento']:
            v = verificacoes_processadas.get(chave_form_selecionada, {})
            if v.get('verificacao_aplicavel') and (v.get('erro') or v.get('passou') is False):
                verificacao_com_falha_ou_erro_para_item_selecionado = True

        if verificacao_com_falha_ou_erro_para_item_selecionado:
            geral_ok_final = False
            print(f"DEBUG: Verificação selecionada '{chave_form_selecionada}' causou reprovação no geral_ok_final.")
            # Não há 'break' aqui, pois se qualquer uma das SELECIONADAS falhar, o status final é False.
            # O debug log ajudará a identificar todas as selecionadas que falharam.

    resultados['geral_ok'] = geral_ok_final
    print(f"DEBUG: --- Finalizando realizar_calculo_completo - geral_ok FINAL (baseado nas seleções): {geral_ok_final} ---")
    return resultados

# --- Rotas Flask ---
def log_message_for_template(message):
    """Helper para permitir `print` dentro do template via `log_message(...)`."""
    print(message)
    return '' # Retorna string vazia para não renderizar nada no HTML

@app.route('/')
def inicio():
    """Renderiza a página inicial da aplicação."""
    return render_template('inicio.html', log_message=log_message_for_template)

@app.route('/novo_dimensionamento')
def formulario():
    """Renderiza o formulário para entrada de dados."""
    global tabelas_madeira 
    try:
        from calculos_madeira import tabelas_madeira as tabelas_importadas
        tabelas_a_passar = tabelas_importadas
    except Exception:
        tabelas_a_passar = tabelas_madeira 
    return render_template('formulario.html', tabelas_madeira=tabelas_a_passar, log_message=log_message_for_template)

@app.route('/calcular', methods=['POST'])
def calcular_e_verificar():
    """
    Recebe os dados do formulário, valida, executa os cálculos e
    renderiza o relatório resumido.
    """
    print("DEBUG: --- Rota /calcular CHAMADA ---")
    input_data_storage_for_link = {} 
    verificacoes_selecionadas_lista = []
    try:
        if not MODULO_CALCULOS_OK: raise ImportError("Módulo de cálculos não carregado.")
        form_data = request.form 
        verificacoes_selecionadas_lista = form_data.getlist('verificacoes_selecionadas') 
        print(f"DEBUG: /calcular - verificacoes_selecionadas_lista DO FORM: {verificacoes_selecionadas_lista}")

        input_data_storage_for_link = {key: form_data.getlist(key) if key == 'verificacoes_selecionadas' else form_data.get(key) for key in form_data}
        print(f"DEBUG: /calcular - input_data_storage_for_link P/ URL: {input_data_storage_for_link}")

        chaves_sel = ['dimensoes', 'tracao_simples', 'tracao_perpendicular', 'compressao_simples_resistencia', 'compressao_perpendicular', 'flexao_simples_reta', 'flexao_obliqua', 'flexotracao', 'flexocompressao', 'cisalhamento', 'estabilidade_lateral', 'flechas_els']
        mostrar_verificacoes = {key: key in verificacoes_selecionadas_lista for key in chaves_sel}
        mostrar_verificacoes.update({
            'compressao_estabilidade': mostrar_verificacoes.get('compressao_simples_resistencia', False),
            'flechas_qp': mostrar_verificacoes.get('flechas_els', False),
            'flechas_vento': mostrar_verificacoes.get('flechas_els', False)
        })
        print(f"DEBUG: /calcular - mostrar_verificacoes: {mostrar_verificacoes}")

        global tabelas_madeira 
        tipo_tabela_val = validar_selecao(form_data.get('tipo_tabela'), 'Tipo de Tabela', ["estrutural", "nativa"])
        classes_validas = list(tabelas_madeira.get(tipo_tabela_val, {}).keys()) if tabelas_madeira.get(tipo_tabela_val) else []
        if not classes_validas: raise ValueError(f"Nenhuma classe de madeira encontrada para o tipo de tabela '{tipo_tabela_val}'.")

        dados_validados = {
            'tipo_tabela': tipo_tabela_val,
            'classe_madeira': validar_selecao(form_data.get('classe_madeira'), 'Classe da Madeira', classes_validas),
            'classe_carregamento': validar_selecao(form_data.get('classe_carregamento'), 'Classe Carregamento', list(kmod1_valores.keys()) if kmod1_valores else []),
            'classe_umidade': validar_selecao(form_data.get('classe_umidade'), 'Classe Umidade', list(kmod2_valores.keys()) if kmod2_valores else []),
            'comprimento_m': validar_float(form_data.get('comprimento'), 'Comprimento (m)', False, False, 0.001),
            'largura_mm': validar_float(form_data.get('largura_mm'), 'Largura (mm)', False, False, 0.1),
            'altura_mm': validar_float(form_data.get('altura_mm'), 'Altura (mm)', False, False, 0.1),
            'tipo_peca_dim': validar_selecao(form_data.get('tipo_peca_dim'), 'Tipo Peça (Dim. Mín.)', ["principal_isolada", "secundaria_isolada", "principal_multipla", "secundaria_multipla"]),
            'alpha_n': validar_float(form_data.get('alpha_n', '1.0'), 'alpha_n', False, False, 1.0, 2.0),
            'Ke_x': validar_float(form_data.get('Ke_x', '1.0'), 'Ke_x', False, False, 0.5),
            'Ke_y': validar_float(form_data.get('Ke_y', '1.0'), 'Ke_y', False, False, 0.5),
            'tipo_madeira_beta_c': validar_selecao(form_data.get('tipo_madeira_beta_c', 'serrada'), 'Tipo Madeira (beta_c)', ['serrada', 'mlc']),
            'N_sd_t0_input': validar_float(form_data.get('tracao_paralela_sd', '0'), 'Tração Paralela ELU (N)', True, False, 0.0),
            'N_sd_c0_input': validar_float(form_data.get('compressao_paralela_sd', '0'), 'Compressão Paralela ELU (N)', True, False, 0.0),
            'N_sd_t90_input': validar_float(form_data.get('tracao_perpendicular_sd', '0'), 'Tração Perp. ELU (N)', True, False, 0.0),
            'N_sd_c90_input': validar_float(form_data.get('compressao_perpendicular_sd', '0'), 'Compressão Perp. ELU (N)', True, False, 0.0),
            'V_sd_input': validar_float(form_data.get('forca_cortante_sd', '0'), 'Força Cortante ELU (N)', True, True), 
            'M_sd_x_Nm_input': validar_float(form_data.get('momento_x_sd', '0'), 'Momento X ELU (N.m)', True, True), 
            'M_sd_y_Nm_input': validar_float(form_data.get('momento_y_sd', '0'), 'Momento Y ELU (N.m)', True, True), 
            'L1_mm': validar_float(form_data.get('L1_mm', '0'), 'L1 (mm)', True, False, 0.0), 
            'carga_els_qp_x': validar_float(form_data.get('carga_els_qp_x', '0'), 'Carga ELS QP X (N/m)', True, True), 
            'carga_els_qp_y': validar_float(form_data.get('carga_els_qp_y', '0'), 'Carga ELS QP Y (N/m)', True, True), 
            'carga_els_vento_x': validar_float(form_data.get('carga_els_vento_x', '0'), 'Carga ELS Vento X (N/m)', True, True), 
            'carga_els_vento_y': validar_float(form_data.get('carga_els_vento_y', '0'), 'Carga ELS Vento Y (N/m)', True, True), 
            'verificacoes_selecionadas': verificacoes_selecionadas_lista 
        }
        dados_validados['comprimento_mm'] = dados_validados['comprimento_m'] * 1000 

        resultados_calculados = realizar_calculo_completo(dados_validados)
        resultados_calculados['mostrar_verificacoes'] = mostrar_verificacoes 
        resultados_calculados['inputs'] = input_data_storage_for_link 

        return render_template('relatorio.html', resultados=resultados_calculados, TOL=TOL, max=max, abs=abs, log_message=log_message_for_template)

    except (ValueError, KeyError, NameError, ImportError, ZeroDivisionError) as e:
        current_inputs_for_error = input_data_storage_for_link if input_data_storage_for_link else dict(request.form) 
        if 'verificacoes_selecionadas' not in current_inputs_for_error: 
            current_inputs_for_error['verificacoes_selecionadas'] = request.form.getlist('verificacoes_selecionadas')
        msg_erro = f"Erro ao processar dados: {str(e)}"
        print(f"Erro /calcular: {msg_erro}\n{traceback.format_exc()}")
        return render_template('erro.html', mensagem=msg_erro, inputs=current_inputs_for_error, log_message=log_message_for_template), 400
    except Exception as e:
        current_inputs_for_error = input_data_storage_for_link if input_data_storage_for_link else dict(request.form)
        if 'verificacoes_selecionadas' not in current_inputs_for_error:
            current_inputs_for_error['verificacoes_selecionadas'] = request.form.getlist('verificacoes_selecionadas')
        print("="*20 + " ERRO INESPERADO (/calcular) " + "="*20); traceback.print_exc(); print("="*68)
        msg_erro = f"Ocorreu um erro inesperado no servidor: {type(e).__name__}"
        return render_template('erro.html', mensagem=msg_erro, inputs=current_inputs_for_error, log_message=log_message_for_template), 500

@app.route('/relatorio_detalhado')
def relatorio_detalhado():
    """
    Renderiza o relatório detalhado com base nos dados passados via query string.
    Esses dados são os mesmos que foram submetidos no formulário original.
    """
    print("DEBUG: --- Rota /relatorio_detalhado CHAMADA ---")
    input_data_from_url = {} 
    try:
        if not MODULO_CALCULOS_OK: raise ImportError("Módulo de cálculos não carregado.")
        print(f"DEBUG: /relatorio_detalhado - request.args: {request.args}") 

        verificacoes_selecionadas_lista = request.args.getlist('verificacoes_selecionadas')
        print(f"DEBUG: /relatorio_detalhado - verificacoes_selecionadas_lista DA URL: {verificacoes_selecionadas_lista}")

        input_data_from_url = {key: request.args.get(key) for key in request.args if key != 'verificacoes_selecionadas'}
        input_data_from_url['verificacoes_selecionadas'] = verificacoes_selecionadas_lista 
        print(f"DEBUG: /relatorio_detalhado - input_data_from_url (para validação): {input_data_from_url}")

        chaves_sel = ['dimensoes', 'tracao_simples', 'tracao_perpendicular', 'compressao_simples_resistencia', 'compressao_perpendicular', 'flexao_simples_reta', 'flexao_obliqua', 'flexotracao', 'flexocompressao', 'cisalhamento', 'estabilidade_lateral', 'flechas_els']
        mostrar_verificacoes = {key: key in verificacoes_selecionadas_lista for key in chaves_sel}
        mostrar_verificacoes.update({ 
            'compressao_estabilidade': mostrar_verificacoes.get('compressao_simples_resistencia', False),
            'flechas_qp': mostrar_verificacoes.get('flechas_els', False),
            'flechas_vento': mostrar_verificacoes.get('flechas_els', False)
        })
        print(f"DEBUG: /relatorio_detalhado - mostrar_verificacoes: {mostrar_verificacoes}")

        global tabelas_madeira
        tipo_tabela_val = validar_selecao(input_data_from_url.get('tipo_tabela'), 'Tipo de Tabela', ["estrutural", "nativa"])
        classes_validas = list(tabelas_madeira.get(tipo_tabela_val, {}).keys()) if tabelas_madeira.get(tipo_tabela_val) else []
        if not classes_validas: raise ValueError(f"Nenhuma classe para tabela '{tipo_tabela_val}'.")

        dados_validados = { 
            'tipo_tabela': tipo_tabela_val,
            'classe_madeira': validar_selecao(input_data_from_url.get('classe_madeira'), 'Classe Madeira', classes_validas),
            'classe_carregamento': validar_selecao(input_data_from_url.get('classe_carregamento'), 'Classe Carregamento', list(kmod1_valores.keys()) if kmod1_valores else []),
            'classe_umidade': validar_selecao(input_data_from_url.get('classe_umidade'), 'Classe Umidade', list(kmod2_valores.keys()) if kmod2_valores else []),
            'comprimento_m': validar_float(input_data_from_url.get('comprimento', input_data_from_url.get('comprimento_m', '0')), 'Comprimento (m)'), 
            'largura_mm': validar_float(input_data_from_url.get('largura_mm', '0'), 'Largura (mm)'),
            'altura_mm': validar_float(input_data_from_url.get('altura_mm', '0'), 'Altura (mm)'),
            'tipo_peca_dim': validar_selecao(input_data_from_url.get('tipo_peca_dim', 'principal_isolada'), 'Tipo Peça'), 
            'alpha_n': validar_float(input_data_from_url.get('alpha_n', '1.0'), 'alpha_n'),
            'Ke_x': validar_float(input_data_from_url.get('Ke_x', '1.0'), 'Ke_x'),
            'Ke_y': validar_float(input_data_from_url.get('Ke_y', '1.0'), 'Ke_y'),
            'tipo_madeira_beta_c': validar_selecao(input_data_from_url.get('tipo_madeira_beta_c', 'serrada'), 'Tipo Madeira (beta_c)'), 
            'N_sd_t0_input': validar_float(input_data_from_url.get('tracao_paralela_sd', input_data_from_url.get('N_sd_t0_input', '0')), 'Tração Paralela'), 
            'N_sd_c0_input': validar_float(input_data_from_url.get('compressao_paralela_sd', input_data_from_url.get('N_sd_c0_input', '0')), 'Compressão Paralela'),
            'N_sd_t90_input': validar_float(input_data_from_url.get('tracao_perpendicular_sd', input_data_from_url.get('N_sd_t90_input', '0')), 'Tração Perp.'),
            'N_sd_c90_input': validar_float(input_data_from_url.get('compressao_perpendicular_sd', input_data_from_url.get('N_sd_c90_input', '0')), 'Compressão Perp.'),
            'V_sd_input': validar_float(input_data_from_url.get('forca_cortante_sd', input_data_from_url.get('V_sd_input', '0')), 'Força Cortante', permitir_negativo=True),
            'M_sd_x_Nm_input': validar_float(input_data_from_url.get('momento_x_sd', input_data_from_url.get('M_sd_x_Nm_input', '0')), 'Momento X', permitir_negativo=True),
            'M_sd_y_Nm_input': validar_float(input_data_from_url.get('momento_y_sd', input_data_from_url.get('M_sd_y_Nm_input', '0')), 'Momento Y', permitir_negativo=True),
            'L1_mm': validar_float(input_data_from_url.get('L1_mm', '0'), 'L1'), 
            'carga_els_qp_x': validar_float(input_data_from_url.get('carga_els_qp_x', '0'), 'Carga QP X', permitir_negativo=True), 
            'carga_els_qp_y': validar_float(input_data_from_url.get('carga_els_qp_y', '0'), 'Carga QP Y', permitir_negativo=True), 
            'carga_els_vento_x': validar_float(input_data_from_url.get('carga_els_vento_x', '0'), 'Carga Vento X', permitir_negativo=True), 
            'carga_els_vento_y': validar_float(input_data_from_url.get('carga_els_vento_y', '0'), 'Carga Vento Y', permitir_negativo=True), 
            'verificacoes_selecionadas': verificacoes_selecionadas_lista
        }
        dados_validados['comprimento_mm'] = dados_validados['comprimento_m'] * 1000
        print(f"DEBUG: /relatorio_detalhado - dados_validados ANTES de calc: verificacoes_selecionadas={dados_validados.get('verificacoes_selecionadas')}")

        resultados_calculados = realizar_calculo_completo(dados_validados)
        resultados_calculados['mostrar_verificacoes'] = mostrar_verificacoes
        resultados_calculados['inputs'] = input_data_from_url 

        return render_template('relatorio_detalhado.html', resultados=resultados_calculados, TOL=TOL, abs=abs, max=max, GAMMA_C=GAMMA_C, GAMMA_T=GAMMA_T, GAMMA_M=GAMMA_M, GAMMA_V=GAMMA_V, log_message=log_message_for_template)

    except (ValueError, KeyError, NameError, ImportError, ZeroDivisionError) as e:
        current_inputs_for_error = input_data_from_url if input_data_from_url else dict(request.args)
        if 'verificacoes_selecionadas' not in current_inputs_for_error:
            current_inputs_for_error['verificacoes_selecionadas'] = request.args.getlist('verificacoes_selecionadas')
        msg_erro = f"Erro ao gerar relatório detalhado: {str(e)}"
        print(f"Erro /relatorio_detalhado: {msg_erro}\n{traceback.format_exc()}")
        return render_template('erro.html', mensagem=msg_erro, inputs=current_inputs_for_error, log_message=log_message_for_template), 400
    except Exception as e:
        current_inputs_for_error = input_data_from_url if input_data_from_url else dict(request.args)
        if 'verificacoes_selecionadas' not in current_inputs_for_error:
            current_inputs_for_error['verificacoes_selecionadas'] = request.args.getlist('verificacoes_selecionadas')
        print("="*20 + " ERRO INESPERADO (/relatorio_detalhado) " + "="*20); traceback.print_exc(); print("="*68)
        msg_erro = f"Ocorreu um erro inesperado no servidor: {type(e).__name__}"
        return render_template('erro.html', mensagem=msg_erro, inputs=current_inputs_for_error, log_message=log_message_for_template), 500

@app.route('/erro')
def pagina_erro():
    """Renderiza uma página de erro genérica."""
    mensagem = request.args.get('mensagem', 'Ocorreu um erro desconhecido.')
    inputs_str = request.args.get('inputs') 
    inputs_dict = {}
    if inputs_str:
        try:
            import ast
            inputs_dict = ast.literal_eval(inputs_str) 
        except:
            inputs_dict = {'raw_inputs_str': inputs_str} if inputs_str else {} 
    return render_template('erro.html', mensagem=mensagem, inputs=inputs_dict, log_message=log_message_for_template)

if __name__ == '__main__':
    porta_app = int(os.environ.get("PORT", 5000)) 
    if not MODULO_CALCULOS_OK:
        print("\n!!! AVISO: O módulo 'calculos_madeira.py' NÃO FOI CARREGADO CORRETAMENTE. !!!")
        print("!!! A aplicação pode não funcionar como esperado. Verifique os erros de importação. !!!\n")
    else:
        print("INFO: Módulo 'calculos_madeira.py' carregado e pronto para uso.")
    print(f"INFO: Servidor Flask iniciando em http://0.0.0.0:{porta_app}")
    app.run(debug=True, host='0.0.0.0', port=porta_app)
