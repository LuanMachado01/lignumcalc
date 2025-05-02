# -*- coding: utf-8 -*-
"""
app.py - Aplicação Flask para Verificação de Elementos de Madeira (NBR 7190-1:2022)

Versão Modificada:
- Calcula k_M (0.7 para retangular, 1.0 para outras) e passa para verificações.
- Passa a função abs() para o template relatorio_detalhado.html.
- Função central `realizar_calculo_completo`.
- Retorna resultados detalhados para memorial.
- Ordem de cálculo de f_d corrigida para dependências (f_t90d, f_c90d).
- Uso correto de f_c0k para Tabela 3.
- Estimativa de f_md para Tabela 2 clarificada.
- Verificação de Tração Perpendicular agora afeta resultado geral.
- Verificação de estabilidade integrada à Compressão e Flexocompressão.
- ATENÇÃO: Compressão Perpendicular ainda usa Área Transversal por padrão.
"""

import math
import re
import traceback
from flask import Flask, render_template, request, url_for

# --- Importação SEGURA do Módulo de Cálculos ---
MODULO_CALCULOS_OK = False
tabelas_madeira = {}
kmod1_valores, kmod2_valores, TOL = {}, {}, 1e-9
GAMMA_M, GAMMA_C, GAMMA_T, GAMMA_V = 1.4, 1.4, 1.4, 1.8

try:
    # Certifique-se que calculos_madeira.py está atualizado
    # Importa as funções necessárias, incluindo as modificadas
    from calculos_madeira import (
        tabelas_madeira, kmod1_valores, kmod2_valores,
        GAMMA_M, GAMMA_C, GAMMA_T, GAMMA_V, TOL,
        calcular_propriedades_geometricas, obter_propriedades_madeira,
        calcular_kmod, calcular_kmod1, calcular_kmod2,
        calcular_f_t0d, calcular_f_t90d, calcular_f_c0d,
        calcular_f_c90d, calcular_f_vd, calcular_f_md,
        obter_E0_med, obter_E0_05, obter_E0_ef,
        verificar_dimensoes_minimas, verificar_tracao_simples,
        verificar_compressao_axial_com_estabilidade,
        verificar_flexocompressao_resistencia,     # k_M agora é parâmetro
        verificar_flexocompressao_com_estabilidade, # k_M agora é parâmetro, retorna 11 valores
        verificar_flexotracao,                      # k_M agora é parâmetro
        verificar_flexao_simples_reta,
        verificar_flexao_obliqua,                   # k_M agora é parâmetro
        verificar_cisalhamento,
        verificar_compressao_perpendicular,
        verificar_estabilidade_lateral_viga,
    )
    MODULO_CALCULOS_OK = True
    print("INFO: Módulo 'calculos_madeira.py' carregado com sucesso.")
except ImportError as e:
    MODULO_CALCULOS_OK = False
    print("*"*60)
    print(" ERRO CRÍTICO: Falha ao importar 'calculos_madeira.py'.")
    print(f" Detalhe: {e}")
    print(" Verifique o arquivo 'calculos_madeira.py'. A aplicação não funcionará corretamente.")
    print("*"*60)
except Exception as e_geral:
    MODULO_CALCULOS_OK = False
    print("*"*60)
    print(f" ERRO CRÍTICO INESPERADO durante a importação: {type(e_geral).__name__}")
    print(f" Detalhe: {e_geral}")
    print("*"*60)


# --- Configuração Flask ---
app = Flask(__name__)
# app.secret_key = 'defina_uma_chave_aqui_se_usar_sessoes'

# --- Funções Auxiliares de Validação ---
def validar_float(valor_str, nome_campo, permitir_zero=True, permitir_negativo=True, minimo=None, maximo=None):
    if valor_str is None or valor_str.strip() == "":
        if permitir_zero: return 0.0
        else: raise ValueError(f"Campo '{nome_campo}' é obrigatório e não pode ser zero.")
    valor_fmt = valor_str.strip().replace(',', '.')
    regex = r'^-?\d+(\.\d+)?$' if permitir_negativo else r'^\d+(\.\d+)?$'
    if not re.match(regex, valor_fmt):
        raise ValueError(f"Formato inválido para '{nome_campo}': '{valor_str}'. Use números (e opcionalmente '.' ou ',').")
    try:
        valor = float(valor_fmt)
        if not permitir_zero and abs(valor) < TOL:
             raise ValueError(f"Campo '{nome_campo}' não pode ser zero (após conversão).")
        if not permitir_negativo and valor < -TOL:
            raise ValueError(f"Campo '{nome_campo}' não pode ser negativo (após conversão).")
        if minimo is not None and valor < minimo - TOL:
             raise ValueError(f"Campo '{nome_campo}' ({valor:.2f}) deve ser >= {minimo}.")
        if maximo is not None and valor > maximo + TOL:
            raise ValueError(f"Campo '{nome_campo}' ({valor:.2f}) deve ser <= {maximo}.")
        if nome_campo == 'alpha_n' and (valor < 1.0 - TOL or valor > 2.0 + TOL):
             raise ValueError(f"Campo '{nome_campo}' ($\alpha_n$) deve estar entre 1.0 e 2.0 (Tabela 6).")
        if nome_campo.startswith('Ke_') and valor < 0.5 - TOL:
             raise ValueError(f"Campo '{nome_campo}' ($K_e$) deve ser >= 0.5 (Tabela 7).")
        return valor
    except ValueError as e:
        if isinstance(e, ValueError) and e.args and isinstance(e.args[0], str) and any(term in e.args[0] for term in ["obrigatório", "deve estar entre", "deve ser >=", "não pode ser zero", "não pode ser negativo", "Formato inválido"]):
             raise e
        else:
             raise ValueError(f"Erro ao processar valor numérico para '{nome_campo}' ('{valor_str}').") from e

def validar_selecao(valor_str, nome_campo, opcoes_validas):
    if not valor_str or valor_str.strip() == "":
        raise ValueError(f"Seleção para '{nome_campo}' é obrigatória.")
    valor = valor_str.strip()
    opcoes_iteraveis = []
    if isinstance(opcoes_validas, dict):
        opcoes_iteraveis = list(opcoes_validas.keys())
    elif hasattr(opcoes_validas, '__iter__') and not isinstance(opcoes_validas, str):
         opcoes_iteraveis = list(opcoes_validas)
    else:
        print(f"AVISO: Opções inválidas ({type(opcoes_validas)}) fornecidas para validação de '{nome_campo}'. Pulando validação.")
        return valor
    if not opcoes_iteraveis:
         print(f"AVISO: Lista de opções válidas para '{nome_campo}' está vazia. Pulando validação.")
         return valor
    if valor not in opcoes_iteraveis:
        op_str = ", ".join(map(str, opcoes_iteraveis))
        if len(op_str) > 150: op_str = op_str[:150] + "..."
        raise ValueError(f"Valor '{valor}' inválido para '{nome_campo}'. Válidos: {op_str}.")
    return valor

# --- Função Central de Cálculo ---
def realizar_calculo_completo(dados_validados):
    """
    Orquestra todos os cálculos e verificações.
    Retorna um dicionário detalhado com todos os resultados intermediários e finais.
    Determina k_M com base na geometria.
    """
    if not MODULO_CALCULOS_OK:
        raise ImportError("Módulo de cálculos não carregado. Verificação impossível.")

    resultados = dados_validados.copy()
    resultados['espessura_min_calculada'] = min(resultados['largura_mm'], resultados['altura_mm'])
    resultados['calculos'] = {}
    resultados['verificacoes'] = {}
    geral_ok = True

    # === Bloco 0: Determinar k_M ===
    try:
        largura = resultados['largura_mm']
        altura = resultados['altura_mm']
        if abs(largura - altura) < TOL:
            k_M_calculado = 1.0
        else:
            k_M_calculado = 0.7
        resultados['calculos']['k_M'] = k_M_calculado
        print(f"INFO: Coeficiente k_M = {k_M_calculado:.1f} (b={largura}, h={altura})")
    except KeyError:
        raise ValueError("Erro ao determinar k_M: Dimensões 'largura_mm' ou 'altura_mm' não encontradas.")
    except Exception as e:
        raise ValueError(f"Erro inesperado ao determinar k_M: {e}")

    # === Bloco 1: Cálculos Iniciais Essenciais ===
    try:
        geom = calcular_propriedades_geometricas(largura, altura)
        resultados['calculos']['geom'] = geom
        props_mad = obter_propriedades_madeira(resultados['tipo_tabela'], resultados['classe_madeira'])
        resultados['calculos']['props_mad'] = props_mad
        tipo_mad_kmod = "serrada" if resultados['tipo_madeira_beta_c'] == 'serrada' else "mlc"
        kmod1 = calcular_kmod1(resultados['classe_carregamento'], tipo_mad_kmod)
        kmod2 = calcular_kmod2(resultados['classe_umidade'], tipo_mad_kmod)
        k_mod = kmod1 * kmod2
        resultados['calculos']['kmod1'] = kmod1
        resultados['calculos']['kmod2'] = kmod2
        resultados['calculos']['k_mod'] = k_mod
        resultados['k_mod'] = k_mod

        f_t0k_val = props_mad.get('f_t0k')
        f_t90k_val = props_mad.get('f_t90k')
        f_c0k_val = props_mad.get('f_c0k')
        f_c90k_val = props_mad.get('f_c90k')
        f_vk_val = props_mad.get('f_vk')
        f_mk_val = props_mad.get('f_mk')

        f_t0d_calculado = calcular_f_t0d(f_t0k_val, k_mod)
        f_c0d_calculado = calcular_f_c0d(f_c0k_val, k_mod)
        f_t90d_calculado = calcular_f_t90d(f_t90k_val, f_t0d_calculado, k_mod)
        f_c90d_calculado = calcular_f_c90d(f_c90k_val, f_c0d_calculado, resultados.get('alpha_n', 1.0), k_mod)
        f_vd_calculado = calcular_f_vd(f_vk_val, k_mod)

        f_mk_para_calculo = f_mk_val
        f_md_estimado_flag = False
        if f_mk_para_calculo is None and resultados['tipo_tabela'] == 'nativa':
            f_md_calculado = f_c0d_calculado
            f_md_estimado_flag = True
            try: resultados['calculos']['f_mk_estimado'] = (f_md_calculado * GAMMA_M) / k_mod if abs(k_mod) > TOL else None
            except Exception: resultados['calculos']['f_mk_estimado'] = None
        elif f_mk_para_calculo is not None:
             f_md_calculado = calcular_f_md(f_mk_para_calculo, k_mod)
        else: raise ValueError(f"f_mk não definido para {resultados['classe_madeira']} ({resultados['tipo_tabela']}) e não é nativa.")

        resultados['calculos']['f_md_estimado'] = f_md_estimado_flag
        resultados['calculos'].update({
            'f_t0k': f_t0k_val, 'f_t90k': f_t90k_val, 'f_c0k': f_c0k_val, 'f_c90k': f_c90k_val,
            'f_vk': f_vk_val, 'f_mk': f_mk_val, 'f_t0d': f_t0d_calculado, 'f_t90d': f_t90d_calculado,
            'f_c0d': f_c0d_calculado, 'f_c90d': f_c90d_calculado, 'f_vd': f_vd_calculado, 'f_md': f_md_calculado
        })

        E_0med = obter_E0_med(props_mad)
        E_005 = obter_E0_05(props_mad)
        E_0ef = obter_E0_ef(props_mad, k_mod)
        resultados['calculos'].update({'E_0med': E_0med, 'E_005': E_005, 'E_0ef': E_0ef})

        beta_c_calc = 0.2 if resultados['tipo_madeira_beta_c'] == 'serrada' else 0.1
        resultados['calculos']['beta_c'] = beta_c_calc
        resultados['beta_c'] = beta_c_calc

    except (ValueError, KeyError, NameError, ZeroDivisionError, TypeError) as e:
        print(f"ERRO CRÍTICO nos cálculos iniciais: {e}")
        traceback.print_exc()
        raise ValueError(f"Falha nos cálculos iniciais: {str(e)}") from e

    # === Bloco 2: Esforços Efetivos ===
    Nsd_t0_calc = resultados['N_sd_t0_input']
    Nsd_c0_calc = resultados['N_sd_c0_input']
    Nsd_t90_calc = resultados['N_sd_t90_input']
    Nsd_c90_calc = resultados['N_sd_c90_input']
    Vsd_calc = abs(resultados['V_sd_input'])
    M_sdx_calc = resultados['M_sd_x_Nm_input'] * 1000
    M_sdy_calc = resultados['M_sd_y_Nm_input'] * 1000
    resultados['calculos']['aplicou_exc_min'] = False
    resultados['calculos']['e_min_mm'] = 0.0
    resultados['calculos']['M_sd_x_Nm_calculado'] = M_sdx_calc / 1000
    resultados['calculos']['M_sd_y_Nm_calculado'] = M_sdy_calc / 1000

    if Nsd_c0_calc > TOL and abs(M_sdx_calc) <= TOL and abs(M_sdy_calc) <= TOL:
        limite_imp = 300.0 if resultados['tipo_madeira_beta_c'] == 'serrada' else 500.0
        if 'comprimento_mm' not in resultados: raise ValueError("Chave 'comprimento_mm' não encontrada.")
        e_min = resultados['comprimento_mm'] / limite_imp
        M_sdx_calc = abs(Nsd_c0_calc * e_min)
        M_sdy_calc = abs(Nsd_c0_calc * e_min)
        resultados['calculos']['aplicou_exc_min'] = True
        resultados['calculos']['e_min_mm'] = e_min
        resultados['calculos']['M_sd_x_Nm_calculado'] = M_sdx_calc / 1000
        resultados['calculos']['M_sd_y_Nm_calculado'] = M_sdy_calc / 1000

    esforcos_calculo = {
        'Nsd_t0': Nsd_t0_calc, 'Nsd_c0': Nsd_c0_calc, 'Nsd_t90': Nsd_t90_calc, 'Nsd_c90': Nsd_c90_calc,
        'Vsd': Vsd_calc, 'Msdx': M_sdx_calc, 'Msdy': M_sdy_calc
    }
    resultados['calculos']['esforcos_finais'] = esforcos_calculo
    resultados['M_sdx_calc_Nmm'] = M_sdx_calc
    resultados['M_sdy_calc_Nmm'] = M_sdy_calc

    # === Bloco 3: Aplicabilidade ===
    is_tension = esforcos_calculo['Nsd_t0'] > TOL
    is_compression = esforcos_calculo['Nsd_c0'] > TOL
    has_moment_x = abs(esforcos_calculo['Msdx']) > TOL
    has_moment_y = abs(esforcos_calculo['Msdy']) > TOL
    has_shear = esforcos_calculo['Vsd'] > TOL
    has_perp_comp = esforcos_calculo['Nsd_c90'] > TOL
    has_perp_tension = esforcos_calculo['Nsd_t90'] > TOL

    aplicabilidade = {
        'dimensoes': True, 'tracao_simples': is_tension, 'tracao_perpendicular': has_perp_tension,
        'compressao_simples_resistencia': is_compression, 'compressao_estabilidade': is_compression,
        'compressao_perpendicular': has_perp_comp, 'flexao_simples_reta': has_moment_x or has_moment_y,
        'flexao_obliqua': has_moment_x and has_moment_y and not is_tension and not is_compression,
        'flexotracao': is_tension and (has_moment_x or has_moment_y),
        'flexocompressao': is_compression and (has_moment_x or has_moment_y),
        'cisalhamento': has_shear, 'estabilidade_lateral': has_moment_x
    }
    is_fsr_applicable_alone = aplicabilidade['flexao_simples_reta'] and not (aplicabilidade['flexao_obliqua'] or aplicabilidade['flexotracao'] or aplicabilidade['flexocompressao'])

    for chave in aplicabilidade.keys():
        if chave not in resultados['verificacoes']:
             resultados['verificacoes'][chave] = {'verificacao_aplicavel': False, 'passou': None, 'erro': None, 'is_combined_case': False, 'esforcos': {}}

    for chave, aplicavel in aplicabilidade.items():
        esforcos_chave = {}
        if 'tracao' in chave and 'perp' not in chave: esforcos_chave['Nsd'] = esforcos_calculo['Nsd_t0']
        if ('compressao_simples_resistencia' in chave or 'compressao_estabilidade' in chave): esforcos_chave['Nsd'] = esforcos_calculo['Nsd_c0']
        elif 'compressao_perpendicular' in chave: esforcos_chave['Nsd'] = esforcos_calculo['Nsd_c90']
        if 'tracao_perpendicular' in chave: esforcos_chave['Nsd'] = esforcos_calculo['Nsd_t90']
        if 'flexao' in chave or 'flexo' in chave or 'estabilidade_lateral' in chave:
            esforcos_chave['Msdx'] = esforcos_calculo['Msdx']
            esforcos_chave['Msdy'] = esforcos_calculo['Msdy']
        if 'cisalhamento' in chave: esforcos_chave['Vsd'] = esforcos_calculo['Vsd']

        verificacao_realmente_aplicavel = aplicavel
        is_combined_case = False
        if chave == 'tracao_simples' and aplicabilidade['flexotracao']: is_combined_case = True
        elif ('compressao_simples_resistencia' in chave or 'compressao_estabilidade' in chave) and aplicabilidade['flexocompressao']: is_combined_case = True
        elif chave == 'flexao_simples_reta' and not is_fsr_applicable_alone:
             verificacao_realmente_aplicavel = False
             is_combined_case = aplicavel

        if chave in resultados['verificacoes']:
             resultados['verificacoes'][chave].update({
                'verificacao_aplicavel': verificacao_realmente_aplicavel, 'is_combined_case': is_combined_case, 'esforcos': esforcos_chave
            })
        else:
            resultados['verificacoes'][chave] = {
                'verificacao_aplicavel': verificacao_realmente_aplicavel, 'passou': None, 'erro': None,
                'is_combined_case': is_combined_case, 'esforcos': esforcos_chave
            }

    # === Bloco 4: Executar Verificações Aplicáveis ===
    calc = resultados['calculos']
    geom = calc['geom']
    verifs = resultados['verificacoes']
    k_M_usar = calc.get('k_M', 0.7) # Pega o k_M calculado no Bloco 0

    # --- Dimensões, Tração Simples, Tração Perpendicular ---
    if verifs['dimensoes']['verificacao_aplicavel']:
        try:
            a_ok, e_ok = verificar_dimensoes_minimas(resultados['largura_mm'], resultados['altura_mm'], resultados['tipo_peca_dim'])
            verifs['dimensoes'].update({'area_ok': a_ok, 'espessura_ok': e_ok, 'passou': a_ok and e_ok})
            if not (a_ok and e_ok): geral_ok = False
        except Exception as e: verifs['dimensoes'].update({'passou': False, 'erro': str(e)}); geral_ok = False
    if verifs['tracao_simples']['verificacao_aplicavel']:
        try:
            p, nsd, nrd = verificar_tracao_simples(esforcos_calculo['Nsd_t0'], geom['area'], calc['f_t0d'])
            verifs['tracao_simples'].update({'passou': p, 'Nsd': nsd, 'NRd': nrd})
            if not p and not verifs['tracao_simples']['is_combined_case']: geral_ok = False
        except Exception as e:
            verifs['tracao_simples'].update({'passou': False, 'erro': str(e)})
            if not verifs['tracao_simples']['is_combined_case']: geral_ok = False
    if verifs['tracao_perpendicular']['verificacao_aplicavel']:
        try:
            nrd_t90 = calc.get('f_t90d', 0.0) * geom.get('area', 0.0)
            nsd_t90 = esforcos_calculo['Nsd_t90']
            passou_t90 = (nsd_t90 <= nrd_t90 + TOL) if nrd_t90 > TOL else abs(nsd_t90) < TOL
            verifs['tracao_perpendicular'].update({'passou': passou_t90, 'Nsd': nsd_t90, 'NRd': nrd_t90})
            if not passou_t90: geral_ok = False
        except Exception as e:
             verifs['tracao_perpendicular'].update({'passou': False, 'erro': str(e), 'NRd': 0.0})
             geral_ok = False

    # --- Compressão Axial (Resistência e Estabilidade) ---
    comp_res_aplicavel = verifs.get('compressao_simples_resistencia', {}).get('verificacao_aplicavel', False)
    comp_est_aplicavel = verifs.get('compressao_estabilidade', {}).get('verificacao_aplicavel', False)
    if comp_res_aplicavel or comp_est_aplicavel:
        try:
            (passou_geral_comp, nsd_comp,
             passou_res_comp, NRd_res_comp,
             passou_est_comp_pura, NRd_est_comp,
             lambda_x_comp, lambda_y_comp, lambda_rel_x_comp, lambda_rel_y_comp,
             kc_x_comp, kc_y_comp,
             esbeltez_ok_comp
            ) = verificar_compressao_axial_com_estabilidade(
                esforcos_calculo['Nsd_c0'], geom['area'], calc['f_c0k'], calc['f_c0d'], calc['E_005'],
                resultados['comprimento_mm'], resultados['Ke_x'], resultados['Ke_y'],
                props_geom=geom, beta_c=calc['beta_c']
            )
            if comp_res_aplicavel:
                 verifs['compressao_simples_resistencia'].update({'passou': passou_res_comp, 'Nsd': nsd_comp, 'NRd': NRd_res_comp})
            if comp_est_aplicavel:
                 verifs['compressao_estabilidade'].update({
                     'passou': passou_est_comp_pura, 'Nsd': nsd_comp, 'NRd': NRd_est_comp,
                     'lambda_x': lambda_x_comp, 'lambda_y': lambda_y_comp,
                     'lambda_rel_x': lambda_rel_x_comp, 'lambda_rel_y': lambda_rel_y_comp,
                     'kc_x': kc_x_comp, 'kc_y': kc_y_comp, 'esbeltez_ok': esbeltez_ok_comp,
                     'lambda_max': max(lambda_x_comp, lambda_y_comp), 'kc_min': min(kc_x_comp, kc_y_comp),
                     'passou_est_apenas': passou_est_comp_pura and esbeltez_ok_comp
                 })
            if not passou_geral_comp and not verifs['compressao_simples_resistencia'].get('is_combined_case', False):
                geral_ok = False
        except Exception as e:
            erro_str = str(e)
            print(f"ERRO na verificação de Compressão Axial: {erro_str}\n{traceback.format_exc()}")
            if comp_res_aplicavel: verifs['compressao_simples_resistencia'].update({'passou': False, 'erro': erro_str})
            if comp_est_aplicavel: verifs['compressao_estabilidade'].update({'passou': False, 'erro': erro_str})
            if not verifs.get('compressao_simples_resistencia', {}).get('is_combined_case', False): geral_ok = False

    # --- Compressão Perpendicular (Usa Area A) ---
    if verifs.get('compressao_perpendicular') and verifs['compressao_perpendicular']['verificacao_aplicavel']:
        try:
            area_apoio_usada = geom['area']
            p, nsd, nrd = verificar_compressao_perpendicular(esforcos_calculo['Nsd_c90'], area_apoio_usada, calc['f_c90d'])
            verifs['compressao_perpendicular'].update({'passou': p, 'Nsd': nsd, 'NRd': nrd, 'Area_apoio_usada': area_apoio_usada})
            if not p: geral_ok = False
        except Exception as e:
             verifs['compressao_perpendicular'].update({'passou': False, 'erro': str(e)})
             geral_ok = False

    # --- Flexão Reta, Oblíqua, Flexotração ---
    if verifs['flexao_simples_reta']['verificacao_aplicavel']:
        passou_flex_x = True; passou_flex_y = True; erro_flex_x = None; erro_flex_y = None
        if abs(esforcos_calculo['Msdx']) > TOL:
            try:
                px, msdx, mrx = verificar_flexao_simples_reta(esforcos_calculo['Msdx'], geom['W_x'], calc['f_md'])
                verifs['flexao_simples_reta']['x'] = {'verificacao_aplicavel': True, 'passou': px, 'Msd': msdx, 'MRd': mrx}
                passou_flex_x = px
            except Exception as e:
                erro_flex_x = str(e); passou_flex_x = False
                verifs['flexao_simples_reta']['x'] = {'verificacao_aplicavel': True, 'passou': False, 'erro': erro_flex_x}
        else: verifs['flexao_simples_reta']['x'] = {'verificacao_aplicavel': False, 'passou': True}
        if abs(esforcos_calculo['Msdy']) > TOL:
             try:
                 py, msdy, mry = verificar_flexao_simples_reta(esforcos_calculo['Msdy'], geom['W_y'], calc['f_md'])
                 verifs['flexao_simples_reta']['y'] = {'verificacao_aplicavel': True, 'passou': py, 'Msd': msdy, 'MRd': mry}
                 passou_flex_y = py
             except Exception as e:
                 erro_flex_y = str(e); passou_flex_y = False
                 verifs['flexao_simples_reta']['y'] = {'verificacao_aplicavel': True, 'passou': False, 'erro': erro_flex_y}
        else: verifs['flexao_simples_reta']['y'] = {'verificacao_aplicavel': False, 'passou': True}
        verifs['flexao_simples_reta']['passou'] = passou_flex_x and passou_flex_y
        if erro_flex_x or erro_flex_y: verifs['flexao_simples_reta']['erro'] = f"X:{erro_flex_x or '-'} | Y:{erro_flex_y or '-'}"
        if not (passou_flex_x and passou_flex_y) and not verifs['flexao_simples_reta']['is_combined_case']: geral_ok = False

    if verifs['flexao_obliqua']['verificacao_aplicavel']:
        try:
            p, ratio = verificar_flexao_obliqua(
                esforcos_calculo['Msdx'], esforcos_calculo['Msdy'],
                geom['W_x'], geom['W_y'], calc['f_md'], k_M=k_M_usar
            )
            verifs['flexao_obliqua'].update({'passou': p, 'ratio': ratio, 'Msdx': esforcos_calculo['Msdx'], 'Msdy': esforcos_calculo['Msdy'], 'k_M_usado': k_M_usar})
            if not p: geral_ok = False
        except Exception as e:
            verifs['flexao_obliqua'].update({'passou': False, 'erro': str(e)})
            geral_ok = False

    if verifs['flexotracao']['verificacao_aplicavel']:
        try:
            p, ratio = verificar_flexotracao(
                esforcos_calculo['Nsd_t0'], esforcos_calculo['Msdx'], esforcos_calculo['Msdy'],
                geom['area'], geom['W_x'], geom['W_y'], calc['f_t0d'], calc['f_md'], k_M=k_M_usar
            )
            verifs['flexotracao'].update({'passou': p, 'ratio': ratio, 'Nsd': esforcos_calculo['Nsd_t0'], 'Msdx': esforcos_calculo['Msdx'], 'Msdy': esforcos_calculo['Msdy'], 'k_M_usado': k_M_usar})
            if not p: geral_ok = False
        except Exception as e:
            verifs['flexotracao'].update({'passou': False, 'erro': str(e)})
            geral_ok = False

    # --- Flexocompressão ---
    if verifs['flexocompressao']['verificacao_aplicavel']:
        passou_fc_res = True; passou_fc_est = True; erro_fc_res = None; erro_fc_est = None
        try:
            p_res, ratio_res = verificar_flexocompressao_resistencia(
                esforcos_calculo['Nsd_c0'], esforcos_calculo['Msdx'], esforcos_calculo['Msdy'],
                geom['area'], geom['W_x'], geom['W_y'], calc['f_c0d'], calc['f_md'], k_M=k_M_usar
            )
            verifs['flexocompressao']['resistencia'] = {
                'passou': p_res, 'ratio': ratio_res, 'Nsd': esforcos_calculo['Nsd_c0'],
                'Msdx': esforcos_calculo['Msdx'], 'Msdy': esforcos_calculo['Msdy'], 'k_M_usado': k_M_usar
            }
            passou_fc_res = p_res
        except Exception as e:
            erro_fc_res = str(e); passou_fc_res = False
            verifs['flexocompressao']['resistencia'] = {'passou': False, 'erro': erro_fc_res}
        try:
            (p_est_geral, ratio_est, lam_x, lam_y, lam_rel_x, lam_rel_y, kcx, kcy,
             lambda_max_fc, esbeltez_ok_fc, passou_ratio_apenas_fc
             ) = verificar_flexocompressao_com_estabilidade(
                esforcos_calculo['Nsd_c0'], esforcos_calculo['Msdx'], esforcos_calculo['Msdy'],
                geom['area'], geom['W_x'], geom['W_y'], calc['f_c0k'], calc['f_c0d'], calc['f_md'],
                calc['E_005'], resultados['comprimento_mm'], resultados['Ke_x'], resultados['Ke_y'],
                props_geom=geom, beta_c=calc['beta_c'], k_M=k_M_usar
            )
            verifs['flexocompressao']['estabilidade'] = {
                'passou': p_est_geral, 'ratio': ratio_est, 'lambda_x': lam_x, 'lambda_y': lam_y,
                'lambda_rel_x': lam_rel_x, 'lambda_rel_y': lam_rel_y, 'kc_x': kcx, 'kc_y': kcy,
                'k_M_usado': k_M_usar, 'lambda_max': lambda_max_fc, 'esbeltez_ok': esbeltez_ok_fc,
                'passou_ratio_apenas': passou_ratio_apenas_fc
            }
            passou_fc_est = p_est_geral
        except Exception as e:
            erro_fc_est = str(e); passou_fc_est = False
            verifs['flexocompressao']['estabilidade'] = {'passou': False, 'erro': erro_fc_est}

        verifs['flexocompressao']['passou'] = passou_fc_res and passou_fc_est
        if erro_fc_res or erro_fc_est: verifs['flexocompressao']['erro'] = f"Res:{erro_fc_res or '-'} | Est:{erro_fc_est or '-'}"
        if not (passou_fc_res and passou_fc_est): geral_ok = False

    # --- Cisalhamento, Estabilidade Lateral ---
    if verifs['cisalhamento']['verificacao_aplicavel']:
        try:
             p, vsd, vrd = verificar_cisalhamento(esforcos_calculo['Vsd'], geom['area'], calc['f_vd'])
             verifs['cisalhamento'].update({'passou': p, 'Vsd': vsd, 'VRd': vrd})
             if not p: geral_ok = False
        except Exception as e:
            verifs['cisalhamento'].update({'passou': False, 'erro': str(e)})
            geral_ok = False
    if verifs['estabilidade_lateral']['verificacao_aplicavel']:
        try:
             resultados_fl = verificar_estabilidade_lateral_viga(
                 resultados['largura_mm'], resultados['altura_mm'], resultados['L1_mm'],
                 calc['E_0med'], calc['f_md'], calc['k_mod'],
                 esforcos_calculo['Msdx'], geom['W_x']
             )
             verifs['estabilidade_lateral'].update(resultados_fl)
             if resultados_fl.get('passou') is False: geral_ok = False
        except Exception as e:
            verifs['estabilidade_lateral'].update({'passou': False, 'erro': str(e)})
            geral_ok = False

    # --- Resultado Geral Final ---
    resultados['geral_ok'] = geral_ok
    return resultados

# --- Rotas da Aplicação Flask ---
@app.route('/')
def inicio():
    return render_template('inicio.html')

@app.route('/novo_dimensionamento')
def formulario():
    return render_template('formulario.html', tabelas_madeira=tabelas_madeira if MODULO_CALCULOS_OK else {})

@app.route('/calcular', methods=['POST'])
def calcular_e_verificar():
    input_data_storage = {}
    verificacoes_selecionadas_lista = []
    try:
        if not MODULO_CALCULOS_OK:
             raise ImportError("Módulo de cálculos ('calculos_madeira.py') não foi carregado com sucesso.")

        form_data = request.form
        input_data_storage = dict(form_data)
        verificacoes_selecionadas_lista = request.form.getlist('verificacoes_selecionadas')
        input_data_storage['verificacoes_selecionadas'] = verificacoes_selecionadas_lista

        chaves_verificacao_selecionaveis = [
            'dimensoes', 'tracao_simples', 'tracao_perpendicular',
            'compressao_simples_resistencia',
            'compressao_perpendicular', 'flexao_simples_reta', 'flexao_obliqua',
            'flexotracao', 'flexocompressao', 'cisalhamento', 'estabilidade_lateral'
        ]
        mostrar_verificacoes = {key: key in verificacoes_selecionadas_lista for key in chaves_verificacao_selecionaveis}
        mostrar_verificacoes['compressao_estabilidade'] = mostrar_verificacoes.get('compressao_simples_resistencia', False)

        tipo_tabela_val = validar_selecao(form_data.get('tipo_tabela'), 'Tipo de Tabela', ["estrutural", "nativa"])
        classes_validas = list(tabelas_madeira.get(tipo_tabela_val, {}).keys()) if MODULO_CALCULOS_OK else []
        dados_validados = {
            'tipo_tabela': tipo_tabela_val,
            'classe_madeira': validar_selecao(form_data.get('classe_madeira'), 'Classe da Madeira', classes_validas),
            'classe_carregamento': validar_selecao(form_data.get('classe_carregamento'), 'Classe de Carregamento', list(kmod1_valores.keys())),
            'classe_umidade': validar_selecao(form_data.get('classe_umidade'), 'Classe de Umidade', list(kmod2_valores.keys())),
            'comprimento_m': validar_float(form_data.get('comprimento'), 'Comprimento (m)', permitir_zero=False, permitir_negativo=False, minimo=0.001),
            'largura_mm': validar_float(form_data.get('largura_mm'), 'Largura (mm)', permitir_zero=False, permitir_negativo=False, minimo=0.1),
            'altura_mm': validar_float(form_data.get('altura_mm'), 'Altura (mm)', permitir_zero=False, permitir_negativo=False, minimo=0.1),
            'tipo_peca_dim': validar_selecao(form_data.get('tipo_peca_dim'), 'Tipo de Peça (Dim. Mínimas)', ["principal_isolada", "secundaria_isolada", "principal_multipla", "secundaria_multipla"]),
            'alpha_n': validar_float(form_data.get('alpha_n', '1.0'), 'alpha_n', permitir_zero=False, permitir_negativo=False, minimo=1.0, maximo=2.0),
            'Ke_x': validar_float(form_data.get('Ke_x', '1.0'), 'Ke_x', permitir_zero=False, permitir_negativo=False, minimo=0.5),
            'Ke_y': validar_float(form_data.get('Ke_y', '1.0'), 'Ke_y', permitir_zero=False, permitir_negativo=False, minimo=0.5),
            'tipo_madeira_beta_c': validar_selecao(form_data.get('tipo_madeira_beta_c', 'serrada'), 'Tipo Madeira (beta_c)', ['serrada', 'mlc']),
            'N_sd_t0_input': validar_float(form_data.get('tracao_paralela_sd', '0'), 'Tração Paralela (N)', permitir_zero=True, permitir_negativo=False),
            'N_sd_c0_input': validar_float(form_data.get('compressao_paralela_sd', '0'), 'Compressão Paralela (N)', permitir_zero=True, permitir_negativo=False),
            'N_sd_t90_input': validar_float(form_data.get('tracao_perpendicular_sd', '0'), 'Tração Perpendicular (N)', permitir_zero=True, permitir_negativo=False),
            'N_sd_c90_input': validar_float(form_data.get('compressao_perpendicular_sd', '0'), 'Compressão Perpendicular (N)', permitir_zero=True, permitir_negativo=False),
            'V_sd_input': validar_float(form_data.get('forca_cortante_sd', '0'), 'Força Cortante (N)', permitir_zero=True, permitir_negativo=True),
            'M_sd_x_Nm_input': validar_float(form_data.get('momento_x_sd', '0'), 'Momento Fletor X (N.m)', permitir_zero=True, permitir_negativo=True),
            'M_sd_y_Nm_input': validar_float(form_data.get('momento_y_sd', '0'), 'Momento Fletor Y (N.m)', permitir_zero=True, permitir_negativo=True),
            'L1_mm': validar_float(form_data.get('L1_mm', '0'), 'L1 (mm)', permitir_zero=True, permitir_negativo=False, minimo=0.0)
        }
        dados_validados['comprimento_mm'] = dados_validados['comprimento_m'] * 1000

        resultados_calculados = realizar_calculo_completo(dados_validados)

        resultados_calculados['mostrar_verificacoes'] = mostrar_verificacoes
        resultados_calculados['verificacoes_selecionadas'] = verificacoes_selecionadas_lista
        resultados_calculados['inputs'] = input_data_storage

        return render_template('relatorio.html', resultados=resultados_calculados, TOL=TOL)

    except (ValueError, KeyError, NameError, ImportError, ZeroDivisionError) as e:
        msg_erro = f"Erro ao processar dados: {str(e)}"
        print(f"Erro na rota /calcular: {msg_erro}\n{traceback.format_exc()}")
        if 'verificacoes_selecionadas' not in input_data_storage:
            input_data_storage['verificacoes_selecionadas'] = request.form.getlist('verificacoes_selecionadas')
        return render_template('erro.html', mensagem=msg_erro, inputs=input_data_storage), 400
    except Exception as e:
        print("="*20 + " ERRO INESPERADO (/calcular) " + "="*20)
        traceback.print_exc()
        print("="*68)
        msg_erro = f"Ocorreu um erro inesperado no servidor: {type(e).__name__}"
        if 'verificacoes_selecionadas' not in input_data_storage:
            input_data_storage['verificacoes_selecionadas'] = request.form.getlist('verificacoes_selecionadas')
        return render_template('erro.html', mensagem=msg_erro, inputs=input_data_storage), 500


@app.route('/relatorio_detalhado')
def relatorio_detalhado():
    input_data_storage = {}
    verificacoes_selecionadas_lista = []
    try:
        if not MODULO_CALCULOS_OK: raise ImportError("Módulo de cálculos não carregado.")

        query_data = request.args.to_dict(flat=False)
        input_data_storage = {k: v[0] if len(v) == 1 else v for k, v in query_data.items()}
        verificacoes_selecionadas_lista = query_data.get('verificacoes_selecionadas[]', query_data.get('verificacoes_selecionadas', []))
        if isinstance(verificacoes_selecionadas_lista, str):
             verificacoes_selecionadas_lista = [verificacoes_selecionadas_lista]
        input_data_storage['verificacoes_selecionadas'] = verificacoes_selecionadas_lista

        mostrar_verificacoes = {
            key: key in verificacoes_selecionadas_lista for key in [
                'dimensoes', 'tracao_simples', 'tracao_perpendicular',
                'compressao_simples_resistencia',
                'compressao_perpendicular', 'flexao_simples_reta', 'flexao_obliqua',
                'flexotracao', 'flexocompressao', 'cisalhamento', 'estabilidade_lateral'
            ]
        }
        mostrar_verificacoes['compressao_estabilidade'] = mostrar_verificacoes.get('compressao_simples_resistencia', False)

        tipo_tabela_val = validar_selecao(input_data_storage.get('tipo_tabela'), 'Tipo de Tabela', ["estrutural", "nativa"])
        classes_validas = list(tabelas_madeira.get(tipo_tabela_val, {}).keys()) if MODULO_CALCULOS_OK else []
        dados_validados = {
            'tipo_tabela': tipo_tabela_val,
            'classe_madeira': validar_selecao(input_data_storage.get('classe_madeira'), 'Classe da Madeira', classes_validas),
            'classe_carregamento': validar_selecao(input_data_storage.get('classe_carregamento'), 'Classe de Carregamento', list(kmod1_valores.keys())),
            'classe_umidade': validar_selecao(input_data_storage.get('classe_umidade'), 'Classe de Umidade', list(kmod2_valores.keys())),
            'comprimento_m': validar_float(input_data_storage.get('comprimento'), 'Comprimento (m)', permitir_zero=False, permitir_negativo=False, minimo=0.001),
            'largura_mm': validar_float(input_data_storage.get('largura_mm'), 'Largura (mm)', permitir_zero=False, permitir_negativo=False, minimo=0.1),
            'altura_mm': validar_float(input_data_storage.get('altura_mm'), 'Altura (mm)', permitir_zero=False, permitir_negativo=False, minimo=0.1),
            'tipo_peca_dim': validar_selecao(input_data_storage.get('tipo_peca_dim', 'principal_isolada'), 'Tipo de Peça (Dim. Mínimas)', ["principal_isolada", "secundaria_isolada", "principal_multipla", "secundaria_multipla"]),
            'alpha_n': validar_float(input_data_storage.get('alpha_n', '1.0'), 'alpha_n', permitir_zero=False, permitir_negativo=False, minimo=1.0, maximo=2.0),
            'Ke_x': validar_float(input_data_storage.get('Ke_x', '1.0'), 'Ke_x', permitir_zero=False, permitir_negativo=False, minimo=0.5),
            'Ke_y': validar_float(input_data_storage.get('Ke_y', '1.0'), 'Ke_y', permitir_zero=False, permitir_negativo=False, minimo=0.5),
            'tipo_madeira_beta_c': validar_selecao(input_data_storage.get('tipo_madeira_beta_c', 'serrada'), 'Tipo Madeira (beta_c)', ['serrada', 'mlc']),
            'N_sd_t0_input': validar_float(input_data_storage.get('tracao_paralela_sd', '0'), 'Tração Paralela (N)', permitir_zero=True, permitir_negativo=False),
            'N_sd_c0_input': validar_float(input_data_storage.get('compressao_paralela_sd', '0'), 'Compressão Paralela (N)', permitir_zero=True, permitir_negativo=False),
            'N_sd_t90_input': validar_float(input_data_storage.get('tracao_perpendicular_sd', '0'), 'Tração Perpendicular (N)', permitir_zero=True, permitir_negativo=False),
            'N_sd_c90_input': validar_float(input_data_storage.get('compressao_perpendicular_sd', '0'), 'Compressão Perpendicular (N)', permitir_zero=True, permitir_negativo=False),
            'V_sd_input': validar_float(input_data_storage.get('forca_cortante_sd', '0'), 'Força Cortante (N)', permitir_zero=True, permitir_negativo=True),
            'M_sd_x_Nm_input': validar_float(input_data_storage.get('momento_x_sd', '0'), 'Momento Fletor X (N.m)', permitir_zero=True, permitir_negativo=True),
            'M_sd_y_Nm_input': validar_float(input_data_storage.get('momento_y_sd', '0'), 'Momento Fletor Y (N.m)', permitir_zero=True, permitir_negativo=True),
            'L1_mm': validar_float(input_data_storage.get('L1_mm', '0'), 'L1 (mm)', permitir_zero=True, permitir_negativo=False, minimo=0.0)
        }
        dados_validados['comprimento_mm'] = dados_validados['comprimento_m'] * 1000

        resultados_calculados = realizar_calculo_completo(dados_validados)

        resultados_calculados['mostrar_verificacoes'] = mostrar_verificacoes
        resultados_calculados['verificacoes_selecionadas'] = verificacoes_selecionadas_lista
        resultados_calculados['inputs'] = input_data_storage

        # Passa 'abs' para o template relatorio_detalhado.html
        return render_template('relatorio_detalhado.html',
                               resultados=resultados_calculados,
                               TOL=TOL,
                               abs=abs) # Passa a função abs

    except (ValueError, KeyError, NameError, ImportError, ZeroDivisionError) as e:
        msg_erro = f"Erro ao gerar relatório detalhado: {str(e)}"
        print(f"Erro na rota /relatorio_detalhado: {msg_erro}\n{traceback.format_exc()}")
        if 'verificacoes_selecionadas' not in input_data_storage:
             input_data_storage['verificacoes_selecionadas'] = request.args.getlist('verificacoes_selecionadas[]', request.args.getlist('verificacoes_selecionadas'))
        return render_template('erro.html', mensagem=msg_erro, inputs=input_data_storage), 400
    except Exception as e:
        print("="*20 + " ERRO INESPERADO (/relatorio_detalhado) " + "="*20)
        traceback.print_exc()
        print("="*68)
        msg_erro = f"Ocorreu um erro inesperado no servidor: {type(e).__name__}"
        if 'verificacoes_selecionadas' not in input_data_storage:
            input_data_storage['verificacoes_selecionadas'] = request.args.getlist('verificacoes_selecionadas[]', request.args.getlist('verificacoes_selecionadas'))
        return render_template('erro.html', mensagem=msg_erro, inputs=input_data_storage), 500

# --- Execução da Aplicação ---
if __name__ == '__main__':
    porta_app = 5000
    if not MODULO_CALCULOS_OK:
        print("\n!!! AVISO: A aplicação iniciará, mas os cálculos falharão devido ao erro na importação de 'calculos_madeira.py' !!!\n")
    else:
        print("Módulo 'calculos_madeira.py' OK.")
    print(f"Servidor Flask iniciando em http://127.0.0.1:{porta_app}")
    app.run(debug=True, host='127.0.0.1', port=porta_app)