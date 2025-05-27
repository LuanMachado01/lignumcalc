# -*- coding: utf-8 -*-
"""
Módulo para cálculo de propriedades de resistência, rigidez e verificações
de estruturas de madeira conforme ABNT NBR 7190-1:2022.

Este módulo contém:
- Constantes de coeficientes de minoração (GAMMA_C, GAMMA_T, etc.).
- Tabelas de propriedades da madeira para classes estruturais e nativas.
- Funções para calcular coeficientes de modificação (kmod).
- Funções para obter propriedades da madeira e módulos de elasticidade.
- Funções para calcular resistências de cálculo (f_d).
- Funções para calcular propriedades geométricas de seções retangulares.
- Funções para realizar verificações de Estados Limites Últimos (ELU), incluindo
  tração, compressão (com estabilidade), flexão, flexotração, flexocompressão
  (com estabilidade), cisalhamento e estabilidade lateral de vigas.
- Funções para realizar verificações de Estados Limites de Serviço (ELS) para flechas.

Referências principais:
- ABNT NBR 7190-1:2022 - Projeto de estruturas de madeira - Parte 1: Critérios de dimensionamento.
"""

import math
import traceback

# --------------------------------------------------------------------------
# Constantes (Coeficientes de Minoração - Item 5.8.5 NBR 7190-1:2022)
# --------------------------------------------------------------------------
GAMMA_C = 1.4  # Coeficiente de minoração para compressão paralela e perpendicular
GAMMA_T = 1.4  # Coeficiente de minoração para tração paralela e perpendicular
GAMMA_M = 1.4  # Coeficiente de minoração para flexão
GAMMA_V = 1.8  # Coeficiente de minoração para cisalhamento
TOL = 1e-9     # Tolerância geral para comparações com zero

# --------------------------------------------------------------------------
# Tabelas de Propriedades da Madeira (NBR 7190-1:2022, Tabelas 2 e 3)
# --------------------------------------------------------------------------
tabelas_madeira = {
    "estrutural": {
        "C14": {"f_mk": 14, "f_t0k": 8, "f_t90k": 0.4, "f_c0k": 16, "f_c90k": 2.0, "f_vk": 3.0, "E_0med": 7000, "E_005": 4700, "E_90med": 200, "G_med": 400, "densidade_k": 290, "densidade_med": 350},
        "C16": {"f_mk": 16, "f_t0k": 10, "f_t90k": 0.4, "f_c0k": 17, "f_c90k": 2.2, "f_vk": 3.2, "E_0med": 8000, "E_005": 5400, "E_90med": 300, "G_med": 500, "densidade_k": 310, "densidade_med": 370},
        "C18": {"f_mk": 18, "f_t0k": 11, "f_t90k": 0.4, "f_c0k": 18, "f_c90k": 2.2, "f_vk": 3.4, "E_0med": 9000, "E_005": 6000, "E_90med": 300, "G_med": 600, "densidade_k": 320, "densidade_med": 380},
        "C20": {"f_mk": 20, "f_t0k": 12, "f_t90k": 0.4, "f_c0k": 19, "f_c90k": 2.3, "f_vk": 3.6, "E_0med": 9500, "E_005": 6400, "E_90med": 300, "G_med": 600, "densidade_k": 330, "densidade_med": 390},
        "C22": {"f_mk": 22, "f_t0k": 13, "f_t90k": 0.4, "f_c0k": 20, "f_c90k": 2.4, "f_vk": 3.8, "E_0med": 10000, "E_005": 6700, "E_90med": 300, "G_med": 600, "densidade_k": 340, "densidade_med": 410},
        "C24": {"f_mk": 24, "f_t0k": 14, "f_t90k": 0.4, "f_c0k": 21, "f_c90k": 2.5, "f_vk": 4.0, "E_0med": 11000, "E_005": 7400, "E_90med": 400, "G_med": 700, "densidade_k": 350, "densidade_med": 420},
        "C27": {"f_mk": 27, "f_t0k": 16, "f_t90k": 0.4, "f_c0k": 22, "f_c90k": 2.6, "f_vk": 4.0, "E_0med": 11500, "E_005": 7700, "E_90med": 400, "G_med": 700, "densidade_k": 370, "densidade_med": 450},
        "C30": {"f_mk": 30, "f_t0k": 18, "f_t90k": 0.4, "f_c0k": 23, "f_c90k": 2.7, "f_vk": 4.0, "E_0med": 12000, "E_005": 8000, "E_90med": 400, "G_med": 800, "densidade_k": 380, "densidade_med": 460},
        "C35": {"f_mk": 35, "f_t0k": 21, "f_t90k": 0.4, "f_c0k": 25, "f_c90k": 2.8, "f_vk": 4.0, "E_0med": 13000, "E_005": 8700, "E_90med": 400, "G_med": 800, "densidade_k": 400, "densidade_med": 480},
        "C40": {"f_mk": 40, "f_t0k": 24, "f_t90k": 0.4, "f_c0k": 26, "f_c90k": 2.9, "f_vk": 4.0, "E_0med": 14000, "E_005": 9400, "E_90med": 500, "G_med": 900, "densidade_k": 420, "densidade_med": 500},
        "C45": {"f_mk": 45, "f_t0k": 27, "f_t90k": 0.4, "f_c0k": 27, "f_c90k": 3.1, "f_vk": 4.0, "E_0med": 15000, "E_005": 10000, "E_90med": 500, "G_med": 900, "densidade_k": 440, "densidade_med": 520},
        "C50": {"f_mk": 50, "f_t0k": 30, "f_t90k": 0.4, "f_c0k": 29, "f_c90k": 3.2, "f_vk": 4.0, "E_0med": 16000, "E_005": 11000, "E_90med": 500, "G_med": 1000, "densidade_k": 460, "densidade_med": 550},
        "D18": {"f_mk": 18, "f_t0k": 11, "f_t90k": 0.6, "f_c0k": 18, "f_c90k": 7.5, "f_vk": 3.4, "E_0med": 9500, "E_005": 8000, "E_90med": 600, "G_med": 600, "densidade_k": 475, "densidade_med": 570},
        "D24": {"f_mk": 24, "f_t0k": 14, "f_t90k": 0.6, "f_c0k": 21, "f_c90k": 7.8, "f_vk": 4.0, "E_0med": 10000, "E_005": 8500, "E_90med": 700, "G_med": 600, "densidade_k": 485, "densidade_med": 580},
        "D30": {"f_mk": 30, "f_t0k": 18, "f_t90k": 0.6, "f_c0k": 23, "f_c90k": 8.0, "f_vk": 4.0, "E_0med": 11000, "E_005": 9200, "E_90med": 700, "G_med": 700, "densidade_k": 530, "densidade_med": 640},
        "D35": {"f_mk": 35, "f_t0k": 21, "f_t90k": 0.6, "f_c0k": 25, "f_c90k": 8.1, "f_vk": 4.0, "E_0med": 12000, "E_005": 10000, "E_90med": 800, "G_med": 800, "densidade_k": 540, "densidade_med": 650},
        "D40": {"f_mk": 40, "f_t0k": 24, "f_t90k": 0.6, "f_c0k": 26, "f_c90k": 8.3, "f_vk": 4.0, "E_0med": 13000, "E_005": 11000, "E_90med": 900, "G_med": 800, "densidade_k": 560, "densidade_med": 660},
        "D50": {"f_mk": 50, "f_t0k": 30, "f_t90k": 0.6, "f_c0k": 29, "f_c90k": 9.3, "f_vk": 4.0, "E_0med": 14000, "E_005": 12000, "E_90med": 900, "G_med": 900, "densidade_k": 620, "densidade_med": 750},
        "D60": {"f_mk": 60, "f_t0k": 36, "f_t90k": 0.6, "f_c0k": 32, "f_c90k": 11.0, "f_vk": 4.5, "E_0med": 17000, "E_005": 14000, "E_90med": 1100, "G_med": 1100, "densidade_k": 700, "densidade_med": 840},
        "D70": {"f_mk": 70, "f_t0k": 42, "f_t90k": 0.6, "f_c0k": 34, "f_c90k": 13.5, "f_vk": 5.0, "E_0med": 20000, "E_005": 16800, "E_90med": 1330, "G_med": 1250, "densidade_k": 900, "densidade_med": 1080}
    },
    "nativa": { # Tabela 2 da NBR 7190-1:2022
        "D20": {"f_c0k": 20, "f_v0k": 4, "E_c0med": 10000, "densidade_med": 500},
        "D30": {"f_c0k": 30, "f_v0k": 5, "E_c0med": 12000, "densidade_med": 625},
        "D40": {"f_c0k": 40, "f_v0k": 6, "E_c0med": 14500, "densidade_med": 750},
        "D50": {"f_c0k": 50, "f_v0k": 7, "E_c0med": 16500, "densidade_med": 850},
        "D60": {"f_c0k": 60, "f_v0k": 8, "E_c0med": 19500, "densidade_med": 1000}
    }
}
# Preenchimento automático de propriedades derivadas para tabela 'nativa'
for classe, props in tabelas_madeira["nativa"].items():
    e_c0med = props.get("E_c0med")
    if e_c0med:
        props["E_0med"] = e_c0med
        props["E_005"] = 0.7 * e_c0med if abs(e_c0med) > TOL else 0.0
        props["E_90med"] = e_c0med / 20.0 if abs(e_c0med) > TOL else 0.0
        props["G_med"] = e_c0med / 16.0 if abs(e_c0med) > TOL else 0.0
    fc0k = props.get("f_c0k")
    if fc0k:
        props["f_t0k"] = props.get("f_t0k", fc0k)
        props["f_mk"] = props.get("f_mk", fc0k)
        props["f_t90k"] = props.get("f_t90k", fc0k * 0.05)
        props["f_c90k"] = props.get("f_c90k", fc0k * 0.25)
    rho_med = props.get("densidade_med")
    if rho_med and abs(rho_med) > TOL:
        props["densidade_k"] = rho_med / 1.2
    props["f_vk"] = props.get("f_v0k")

kmod1_valores = { # Tabela 4 NBR 7190:2022
    "permanente": 0.60, "longa": 0.70, "media": 0.80, "curta": 0.90, "instantanea": 1.10,
}
kmod2_valores = { # Tabela 5 NBR 7190:2022
    "classe_1": 1.00, "classe_2": 0.90, "classe_3": 0.80, "classe_4": 0.70
}
kmod_fluencia_valores = { # Tabela 20 NBR 7190:2022
    "serrada": {"classe_1": 0.6, "classe_2": 0.8, "classe_3": 0.8, "classe_4": 2.0},
    "mlc":     {"classe_1": 0.6, "classe_2": 0.8, "classe_3": 0.8, "classe_4": 2.0},
    "mlcc":    {"classe_1": 0.6, "classe_2": 0.8, "classe_3": 0.8, "classe_4": None},
    "lvl":     {"classe_1": 0.6, "classe_2": 0.8, "classe_3": 0.8, "classe_4": 2.0},
    "rolica":  {"classe_1": 0.6, "classe_2": 0.8, "classe_3": 0.8, "classe_4": 2.0},
    "compensado": {"classe_1": 0.8, "classe_2": 1.0, "classe_3": 1.0, "classe_4": 2.5},
    "osb":     {"classe_1": 1.5, "classe_2": 2.25,"classe_3": 2.25,"classe_4": None}
}

# --------------------------------------------------------------------------
# Funções de Cálculo Kmod
# --------------------------------------------------------------------------
def calcular_kmod1(classe_carregamento, tipo_madeira="serrada"):
    """
    Calcula o coeficiente kmod1 conforme Tabela 4 da NBR 7190-1:2022.

    Args:
        classe_carregamento (str): Classe de carregamento ('permanente', 'longa', etc.).
        tipo_madeira (str, optional): Tipo de madeira ('serrada', 'mlc', etc.).
                                     Atualmente, a Tabela 4 diferencia madeira serrada/MLC/etc.
                                     de madeira recomposta. Esta função usa a coluna de
                                     madeira serrada/MLC por padrão.

    Returns:
        float: O valor de kmod1.

    Raises:
        ValueError: Se a classe_carregamento for inválida.
    """
    # Esta implementação simplifica e usa a coluna de "Madeira serrada / Madeira roliça /
    # Madeira lamelada colada (MLC) / Madeira lamelada colada cruzada (MLCC) /
    # Madeira laminada colada (LVL)" da Tabela 4.
    # Se "Madeira recomposta" for considerada, esta função precisará ser ajustada.
    kmod1 = kmod1_valores.get(classe_carregamento)
    if kmod1 is None:
        raise ValueError(f"Classe de carregamento '{classe_carregamento}' inválida.")
    return kmod1

def calcular_kmod2(classe_umidade, tipo_madeira="serrada"):
    """
    Calcula o coeficiente kmod2 conforme Tabela 5 da NBR 7190-1:2022.

    Args:
        classe_umidade (str): Classe de umidade ('classe_1', 'classe_2', etc.).
        tipo_madeira (str, optional): Tipo de madeira ('serrada', 'mlc', 'mlcc', etc.).
                                     Atualmente, a Tabela 5 diferencia madeira serrada/MLC/etc.
                                     de madeira recomposta. Esta função usa a coluna de
                                     madeira serrada/MLC por padrão.

    Returns:
        float: O valor de kmod2.

    Raises:
        ValueError: Se a classe_umidade for inválida ou se a combinação
                    tipo_madeira e classe_umidade for proibida (ex: MLCC em Classe 4).
    """
    # Esta implementação simplifica e usa a coluna de "Madeira serrada / Madeira roliça /
    # Madeira lamelada colada (MLC) / Madeira lamelada colada cruzada (MLCC) /
    # Madeira laminada colada (LVL)" da Tabela 5.
    if tipo_madeira == "mlcc" and classe_umidade == "classe_4":
         raise ValueError("MLCC não é permitido para classe de umidade 4 (NBR 7190:2022 Tabela 5, nota a).")

    if tipo_madeira not in ["serrada", "mlc", "mlcc", "lvl", "rolica"]:
        # Se for um tipo não explicitamente listado para kmod2 na Tabela 5,
        # como "compensado" ou "osb" (que têm colunas próprias na Tabela 20 para fluência,
        # mas não na Tabela 5 para kmod2), assume-se comportamento de madeira serrada.
        # A NBR não especifica kmod2 para madeira recomposta diretamente nas tabelas principais de kmod.
        # No entanto, a Tabela 5 possui uma coluna "Madeira recomposta".
        # Se `tipo_madeira` for explicitamente "recomposta", essa lógica precisaria ser ajustada.
        # Por ora, se não for um dos tipos principais, imprime um aviso e usa o valor de serrada.
        print(f"AVISO: Tipo de madeira '{tipo_madeira}' não mapeado explicitamente para kmod2 na Tabela 5. Usando valores de madeira serrada/MLC.")

    kmod2 = kmod2_valores.get(classe_umidade)
    if kmod2 is None:
        raise ValueError(f"Classe de umidade '{classe_umidade}' inválida.")
    return kmod2

def calcular_kmod(classe_carregamento, classe_umidade, tipo_madeira="serrada"):
    """
    Calcula o coeficiente de modificação total kmod (kmod1 * kmod2).
    Ref: NBR 7190-1:2022, Item 5.8.4.

    Args:
        classe_carregamento (str): Classe de carregamento.
        classe_umidade (str): Classe de umidade.
        tipo_madeira (str, optional): Tipo de madeira. Default é "serrada".

    Returns:
        float: O valor total de kmod.
    """
    kmod1 = calcular_kmod1(classe_carregamento, tipo_madeira)
    kmod2 = calcular_kmod2(classe_umidade, tipo_madeira)
    return kmod1 * kmod2

# --------------------------------------------------------------------------
# Obter Propriedades da Madeira e Módulos de Elasticidade
# --------------------------------------------------------------------------
def obter_E0_med(propriedades):
    """
    Obtém o módulo de elasticidade médio na direção paralela às fibras (E_0,med).
    Para madeiras nativas (Tabela 2), E_0,med é assumido igual a E_c0,med.
    Ref: NBR 7190-1:2022, Item 5.8.7.

    Args:
        propriedades (dict): Dicionário com as propriedades da classe de madeira.

    Returns:
        float: Valor de E_0,med.

    Raises:
        KeyError: Se E_0med (ou E_c0med para nativas) não for encontrado.
        ValueError: Se o valor encontrado for inválido.
    """
    e0_med = propriedades.get("E_0med")
    if e0_med is None:
        e0_med = propriedades.get("E_c0med") # Fallback para Tabela 2 (nativas)
    if e0_med is None:
        raise KeyError("E_0med (ou E_c0med para Tabela 2) não encontrado nas propriedades da madeira.")
    if not isinstance(e0_med, (int, float)) or e0_med <= TOL:
        raise ValueError(f"Valor de E_0med ({e0_med}) inválido. Deve ser um número positivo.")
    return e0_med

def obter_G_med(propriedades):
    """
    Obtém o módulo de elasticidade transversal médio (G_med).
    Se G_med não estiver diretamente na tabela, é estimado como E_0,med / 16.
    Ref: NBR 7190-1:2022, Item 5.8.7, Eq. 5.

    Args:
        propriedades (dict): Dicionário com as propriedades da classe de madeira.

    Returns:
        float or None: Valor de G_med, ou None se não puder ser calculado.
    """
    g_med_tabela = propriedades.get("G_med")
    if g_med_tabela is not None:
        if not isinstance(g_med_tabela, (int, float)) or g_med_tabela <= TOL:
            print(f"AVISO: G_med da tabela ({g_med_tabela}) é inválido. Tentando estimar.")
        else:
            return g_med_tabela
    try:
        e0_med = obter_E0_med(propriedades)
        return e0_med / 16.0
    except (KeyError, ValueError) as e:
        print(f"AVISO: Não foi possível calcular G_med a partir de E_0,med devido a: {e}. Retornando None.")
        return None

def obter_propriedades_madeira(tipo_tabela, classe_madeira):
    """
    Busca as propriedades da madeira de `tabelas_madeira` e adiciona G_med calculado.

    Args:
        tipo_tabela (str): 'estrutural' (Tabela 3) ou 'nativa' (Tabela 2).
        classe_madeira (str): A classe de resistência da madeira (ex: 'C20', 'D30').

    Returns:
        dict: Dicionário com as propriedades da madeira, incluindo G_med.

    Raises:
        ValueError: Se o tipo_tabela for inválido.
        KeyError: Se a classe_madeira for inválida ou se propriedades essenciais faltarem.
    """
    tabela_selecionada = tabelas_madeira.get(tipo_tabela)
    if not tabela_selecionada:
        raise ValueError(f"Tipo de tabela '{tipo_tabela}' inválido. Use 'estrutural' ou 'nativa'.")

    propriedades = tabela_selecionada.get(classe_madeira)
    if not propriedades:
        raise KeyError(f"Classe de madeira '{classe_madeira}' inválida ou não encontrada para a tabela '{tipo_tabela}'.")

    # Validação de chaves essenciais para garantir que os cálculos subsequentes funcionem
    chaves_essenciais_elu = ["f_c0k", "f_vk"] # f_vk é usado no lugar de f_v0k internamente
    chaves_essenciais_els_rigidez = ["E_0med", "E_c0med"] # Pelo menos um deve existir
    chaves_essenciais_estabilidade = ["E_005"]

    for chave in chaves_essenciais_elu:
         if propriedades.get(chave) is None:
             raise KeyError(f"Propriedade essencial para ELU '{chave}' não encontrada para {tipo_tabela} {classe_madeira}.")
    if not any(propriedades.get(chave) for chave in chaves_essenciais_els_rigidez):
         raise KeyError(f"Propriedade essencial para ELS ('E_0med' ou 'E_c0med') não encontrada para {tipo_tabela} {classe_madeira}.")
    # E_005 é calculado para 'nativa', então só checa se não for 'nativa'
    if tipo_tabela != 'nativa' and propriedades.get("E_005") is None:
         raise KeyError(f"Propriedade essencial para Estabilidade 'E_005' não encontrada para {tipo_tabela} {classe_madeira}.")

    # Adiciona G_med ao dicionário de propriedades se ainda não estiver lá ou precisar ser recalculado
    # A lógica de preenchimento da tabela 'nativa' já calcula G_med, mas esta garante.
    if 'G_med' not in propriedades or propriedades['G_med'] is None:
        propriedades['G_med'] = obter_G_med(propriedades.copy()) # Passa uma cópia para evitar modificar o original na chamada

    return propriedades.copy() # Retorna uma cópia para evitar modificação externa da tabela original

def obter_E0_05(propriedades):
    """
    Obtém o módulo de elasticidade característico E_0,05.
    Para madeiras nativas (Tabela 2), E_0,05 é estimado como 0.7 * E_c0,med.
    Ref: NBR 7190-1:2022, Item 5.8.7, Eq. 3.

    Args:
        propriedades (dict): Dicionário com as propriedades da classe de madeira.

    Returns:
        float: Valor de E_0,05.

    Raises:
        KeyError: Se E_005 (ou E_c0med para estimativa) não for encontrado.
        ValueError: Se o valor encontrado ou usado para estimativa for inválido.
    """
    e0_05 = propriedades.get("E_005") # E_005 já está preenchido para ambas as tabelas
    if e0_05 is None:
        raise KeyError("E_005 não encontrado nas propriedades da madeira.")
    if not isinstance(e0_05, (int, float)) or e0_05 <= TOL:
        raise ValueError(f"Valor de E_005 ({e0_05}) inválido. Deve ser um número positivo.")
    return e0_05

def obter_E0_ef(propriedades, k_mod):
    """
    Calcula o módulo de elasticidade efetivo E_0,ef para verificação de estabilidade lateral em ELU.
    Ref: NBR 7190-1:2022, Item 5.8.7, Eq. 4.

    Args:
        propriedades (dict): Dicionário com as propriedades da classe de madeira.
        k_mod (float): Coeficiente de modificação total.

    Returns:
        float: Valor de E_0,ef.
    """
    e0_med = obter_E0_med(propriedades) # Já levanta exceção se e0_med for inválido
    if abs(k_mod) < TOL:
        return 0.0 # Se k_mod é zero, E0_ef é zero
    return k_mod * e0_med

# --------------------------------------------------------------------------
# Calcular Resistências de Cálculo (f_d) - ELU
# --------------------------------------------------------------------------
def calcular_f_t0d(f_t0k, k_mod):
    """
    Calcula a resistência de cálculo à tração paralela às fibras (f_t0,d).
    Ref: NBR 7190-1:2022, Item 6.2.6, Eq. 7.

    Args:
        f_t0k (float): Resistência característica à tração paralela.
        k_mod (float): Coeficiente de modificação total.

    Returns:
        float: Valor de f_t0,d. Retorna 0.0 se f_t0k for None ou k_mod for zero.
    """
    if f_t0k is None: return 0.0
    if abs(k_mod) < TOL: return 0.0
    return k_mod * f_t0k / GAMMA_T

def calcular_f_t90d(f_t90k, f_t0d_calc, k_mod):
    """
    Calcula a resistência de cálculo à tração perpendicular às fibras (f_t90,d).
    Considera o limite de 0.06 * f_t0,d.
    Ref: NBR 7190-1:2022, Item 6.2.3 e Item 6.2.6.

    Args:
        f_t90k (float): Resistência característica à tração perpendicular.
        f_t0d_calc (float): Resistência de cálculo à tração paralela já calculada.
        k_mod (float): Coeficiente de modificação total.

    Returns:
        float: Valor de f_t90,d.
    """
    if f_t90k is None: f_t90k = 0.0 # Se f_t90k não fornecido, assume 0
    if abs(k_mod) < TOL: return 0.0

    f_t90d_base = k_mod * f_t90k / GAMMA_T
    limite_norma = 0.06 * f_t0d_calc if f_t0d_calc is not None and f_t0d_calc > TOL else float('inf')

    if limite_norma <= TOL: # Se f_t0d_calc for muito pequeno ou zero
        return f_t90d_base
    else:
        return min(f_t90d_base, limite_norma)

def calcular_f_c0d(f_c0k, k_mod):
    """
    Calcula a resistência de cálculo à compressão paralela às fibras (f_c0,d).
    Ref: NBR 7190-1:2022, Item 6.2.6, Eq. 7.

    Args:
        f_c0k (float): Resistência característica à compressão paralela.
        k_mod (float): Coeficiente de modificação total.

    Returns:
        float: Valor de f_c0,d.

    Raises:
        ValueError: Se f_c0k for None ou não positivo.
    """
    if f_c0k is None or f_c0k <= TOL:
        raise ValueError("f_c0k não pode ser None ou não positivo para calcular f_c0d.")
    if abs(k_mod) < TOL: return 0.0
    return k_mod * f_c0k / GAMMA_C

def calcular_f_c90d(f_c90k, f_c0d_calc, alpha_n, k_mod):
    """
    Calcula a resistência de cálculo à compressão perpendicular às fibras (f_c90,d).
    Considera o limite de 0.25 * f_c0,d * alpha_n.
    Ref: NBR 7190-1:2022, Item 6.3.3 e Item 6.2.6.

    Args:
        f_c90k (float): Resistência característica à compressão perpendicular.
        f_c0d_calc (float): Resistência de cálculo à compressão paralela já calculada.
        alpha_n (float): Coeficiente de ajuste para extensão do carregamento (Tabela 6).
        k_mod (float): Coeficiente de modificação total.

    Returns:
        float: Valor de f_c90,d.
    """
    if f_c90k is None: return 0.0
    if abs(k_mod) < TOL: return 0.0

    f_c90d_base = k_mod * f_c90k / GAMMA_C

    if f_c0d_calc is None or f_c0d_calc < TOL: # f_c0d_calc pode ser zero se f_c0k for zero, mas já validado
         print("AVISO: f_c0d_calc inválido para calcular o limite de f_c90d. Usando valor base de f_c90d.")
         return f_c90d_base

    limite_superior_norma = 0.25 * f_c0d_calc * alpha_n
    return min(f_c90d_base, limite_superior_norma)

def calcular_f_vd(f_vk, k_mod):
    """
    Calcula a resistência de cálculo ao cisalhamento (f_v,d).
    f_vk é usado como termo genérico para f_v0k (Tabela 2) ou f_vk (Tabela 3).
    Ref: NBR 7190-1:2022, Item 6.2.6, Eq. 7.

    Args:
        f_vk (float): Resistência característica ao cisalhamento.
        k_mod (float): Coeficiente de modificação total.

    Returns:
        float: Valor de f_v,d.

    Raises:
        ValueError: Se f_vk for None ou não positivo.
    """
    if f_vk is None or f_vk <= TOL:
        raise ValueError("f_vk (ou f_v0k) não pode ser None ou não positivo para calcular f_vd.")
    if abs(k_mod) < TOL: return 0.0
    return k_mod * f_vk / GAMMA_V

def calcular_f_md(f_mk, f_c0d_calc, k_mod, tipo_tabela):
    """
    Calcula a resistência de cálculo à flexão (f_m,d).
    Para Tabela 2 (nativa), assume f_m,d = f_c0,d (Item 6.3.4).
    Para Tabela 3 (estrutural), usa f_mk.
    Ref: NBR 7190-1:2022, Item 6.3.4 e Item 6.2.6.

    Args:
        f_mk (float or None): Resistência característica à flexão (da Tabela 3).
                              Pode ser None se tipo_tabela for 'nativa'.
        f_c0d_calc (float or None): Resistência de cálculo à compressão paralela.
                                     Necessário se tipo_tabela for 'nativa'.
        k_mod (float): Coeficiente de modificação total.
        tipo_tabela (str): 'estrutural' ou 'nativa'.

    Returns:
        float: Valor de f_m,d.

    Raises:
        ValueError: Se inputs necessários estiverem faltando ou tipo_tabela for inválido.
    """
    if tipo_tabela == 'nativa':
        if f_c0d_calc is None:
             raise ValueError("f_c0d_calc deve ser fornecido para calcular f_md para Tabela 2 (nativa).")
        return f_c0d_calc # Conforme Item 6.3.4: "no caso de uso da Tabela 2 considerar fm,d = fc0,d"
    elif tipo_tabela == 'estrutural':
        if f_mk is None:
             raise ValueError("f_mk deve ser fornecido da Tabela 3 para calcular f_md para madeiras estruturais.")
        if abs(k_mod) < TOL: return 0.0
        return k_mod * f_mk / GAMMA_M
    else:
        raise ValueError(f"Tipo de tabela '{tipo_tabela}' desconhecido para cálculo de f_md.")

# --------------------------------------------------------------------------
# Cálculos Geométricos
# --------------------------------------------------------------------------
def calcular_propriedades_geometricas(largura_b, altura_h):
    """
    Calcula propriedades geométricas para uma seção retangular.

    Args:
        largura_b (float): Largura da seção (mm).
        altura_h (float): Altura da seção (mm).

    Returns:
        dict: Dicionário com 'area', 'I_x', 'I_y', 'W_x', 'W_y', 'i_x', 'i_y'.

    Raises:
        ValueError: Se largura_b ou altura_h não forem positivos.
    """
    if largura_b <= TOL or altura_h <= TOL:
        raise ValueError(f"Dimensões da seção b ({largura_b}) e h ({altura_h}) devem ser positivas.")

    area = largura_b * altura_h
    # Momento de inércia em relação ao eixo x (eixo horizontal que passa pelo centroide)
    # A flexão ocorre em torno deste eixo quando a carga é vertical (na direção de h)
    i_x = (largura_b * altura_h**3) / 12.0
    # Momento de inércia em relação ao eixo y (eixo vertical que passa pelo centroide)
    # A flexão ocorre em torno deste eixo quando a carga é horizontal (na direção de b)
    i_y = (altura_h * largura_b**3) / 12.0

    # Módulo de resistência
    w_x = i_x / (altura_h / 2.0) if abs(altura_h) > TOL else 0.0
    w_y = i_y / (largura_b / 2.0) if abs(largura_b) > TOL else 0.0

    # Raio de giração
    raio_ix = math.sqrt(i_x / area) if area > TOL and i_x >= 0 else 0.0
    raio_iy = math.sqrt(i_y / area) if area > TOL and i_y >= 0 else 0.0

    return {"area": area, "I_x": i_x, "I_y": i_y, "W_x": w_x, "W_y": w_y, "i_x": raio_ix, "i_y": raio_iy}

# --------------------------------------------------------------------------
# Verificações ELU (Estado Limite Último)
# --------------------------------------------------------------------------

def verificar_tracao_simples(N_sd_t, A, f_t0d):
    """
    Verifica a peça sob tração simples paralela às fibras (ELU).
    Ref: NBR 7190-1:2022, Item 6.3.2, Eq. 6.

    Args:
        N_sd_t (float): Força normal de tração solicitante de cálculo (N).
        A (float): Área da seção transversal líquida (mm²).
        f_t0d (float): Resistência de cálculo à tração paralela (MPa).

    Returns:
        tuple: (passou (bool), N_sd_t (float), N_Rd_t (float), ratio (float))
    """
    if A <= TOL: return False, abs(N_sd_t), 0.0, float('inf') if abs(N_sd_t) > TOL else 0.0
    if f_t0d <= TOL: # Se resistência é zero ou negligível
        passou = abs(N_sd_t) < TOL # Passa apenas se esforço também for zero
        return passou, abs(N_sd_t), 0.0, 0.0 if passou else float('inf')

    N_Rd_t = f_t0d * A  # Força resistente de cálculo
    passou = abs(N_sd_t) <= N_Rd_t + TOL
    ratio = abs(N_sd_t) / N_Rd_t if N_Rd_t > TOL else (0.0 if passou else float('inf'))
    return passou, abs(N_sd_t), N_Rd_t, ratio

def verificar_compressao_perpendicular(N_sd_90, area_apoio, f_c90d):
    """
    Verifica a peça sob compressão perpendicular às fibras (ELU).
    Ref: NBR 7190-1:2022, Item 6.3.3, Eq. (sem número, sigma_90,d <= fc90,d).

    Args:
        N_sd_90 (float): Força normal de compressão perpendicular solicitante de cálculo (N).
        area_apoio (float): Área de contato efetiva da compressão perpendicular (mm²).
                            Pode ser a área total (A) ou uma área de apoio específica.
        f_c90d (float): Resistência de cálculo à compressão perpendicular (MPa).

    Returns:
        tuple: (passou (bool), N_sd_90 (float), N_Rd_90 (float), ratio (float))
    """
    if area_apoio <= TOL: return False, abs(N_sd_90), 0.0, float('inf') if abs(N_sd_90) > TOL else 0.0
    if f_c90d <= TOL:
        passou = abs(N_sd_90) < TOL
        return passou, abs(N_sd_90), 0.0, 0.0 if passou else float('inf')

    N_Rd_90 = f_c90d * area_apoio # Força resistente de cálculo
    passou = abs(N_sd_90) <= N_Rd_90 + TOL
    ratio = abs(N_sd_90) / N_Rd_90 if N_Rd_90 > TOL else (0.0 if passou else float('inf'))
    return passou, abs(N_sd_90), N_Rd_90, ratio

def verificar_cisalhamento(V_sd, A, f_vd):
    """
    Verifica a peça sob cisalhamento longitudinal em vigas retangulares (ELU).
    Assume tau_d = 1.5 * |V_sd| / A.
    Ref: NBR 7190-1:2022, Item 6.4.2, Eq. 10.

    Args:
        V_sd (float): Força cortante solicitante de cálculo (N). (Sinal não importa aqui).
        A (float): Área da seção transversal bruta (mm²).
        f_vd (float): Resistência de cálculo ao cisalhamento (MPa).

    Returns:
        tuple: (passou (bool), V_sd_abs (float), V_Rd (float), ratio (float))
    """
    V_sd_abs = abs(V_sd)
    if A <= TOL: return False, V_sd_abs, 0.0, float('inf') if V_sd_abs > TOL else 0.0
    if f_vd <= TOL:
        passou = V_sd_abs < TOL
        return passou, V_sd_abs, 0.0, 0.0 if passou else float('inf')

    # Da equação tau_d = 1.5 * V_sd / A <= f_vd, temos V_sd <= (f_vd * A) / 1.5
    V_Rd = (f_vd * A) / 1.5 # Força cortante resistente de cálculo
    passou = V_sd_abs <= V_Rd + TOL
    ratio = V_sd_abs / V_Rd if V_Rd > TOL else (0.0 if passou else float('inf'))
    return passou, V_sd_abs, V_Rd, ratio

def verificar_flexao_simples_reta(M_sd, W, f_md):
    """
    Verifica a peça sob flexão simples reta (ELU).
    Ref: NBR 7190-1:2022, Item 6.3.4, Eq. (sem número, sigma_M,d <= fm,d).

    Args:
        M_sd (float): Momento fletor solicitante de cálculo (N.mm). (Sinal não importa aqui).
        W (float): Módulo de resistência da seção (mm³).
        f_md (float): Resistência de cálculo à flexão (MPa).

    Returns:
        tuple: (passou (bool), M_sd_abs (float), M_Rd (float), ratio (float))
    """
    M_sd_abs = abs(M_sd)
    if W <= TOL: return False, M_sd_abs, 0.0, float('inf') if M_sd_abs > TOL else 0.0
    if f_md <= TOL:
        passou = M_sd_abs < TOL
        return passou, M_sd_abs, 0.0, 0.0 if passou else float('inf')

    M_Rd = f_md * W # Momento fletor resistente de cálculo
    passou = M_sd_abs <= M_Rd + TOL
    ratio = M_sd_abs / M_Rd if M_Rd > TOL else (0.0 if passou else float('inf'))
    return passou, M_sd_abs, M_Rd, ratio

def verificar_flexao_obliqua(M_sdx, M_sdy, Wx, Wy, f_md, k_M):
    """
    Verifica a peça sob flexão simples oblíqua (ELU).
    Ref: NBR 7190-1:2022, Item 6.3.5, Eq. 9.

    Args:
        M_sdx (float): Momento solicitante de cálculo em torno do eixo x (N.mm).
        M_sdy (float): Momento solicitante de cálculo em torno do eixo y (N.mm).
        Wx (float): Módulo de resistência em relação ao eixo x (mm³).
        Wy (float): Módulo de resistência em relação ao eixo y (mm³).
        f_md (float): Resistência de cálculo à flexão (MPa).
        k_M (float): Coeficiente de correção (0.7 para retangular, 1.0 para outras).

    Returns:
        tuple: (passou (bool), ratio_max (float))
               ratio_max é o maior valor das duas equações de interação.
    """
    if Wx <= TOL or Wy <= TOL: return False, float('inf') # Evita divisão por zero
    if f_md <= TOL: # Se resistência é zero
        passou_sem_resistencia = (abs(M_sdx) < TOL and abs(M_sdy) < TOL)
        return passou_sem_resistencia, 0.0 # Passa se não houver momentos

    sigma_Mx_d = abs(M_sdx) / Wx
    sigma_My_d = abs(M_sdy) / Wy

    # Termos da equação de interação
    termo_x = sigma_Mx_d / f_md
    termo_y = sigma_My_d / f_md

    # Duas condições da Eq. 9
    ratio1 = termo_x + k_M * termo_y
    ratio2 = k_M * termo_x + termo_y
    ratio_max = max(ratio1, ratio2)

    passou = ratio_max <= 1.0 + TOL
    return passou, ratio_max

def verificar_flexotracao(N_sd_t, M_sdx, M_sdy, A, Wx, Wy, f_t0d, f_md, k_M):
    """
    Verifica a peça sob flexotração (ELU).
    Ref: NBR 7190-1:2022, Item 6.3.6, Eq. (sem número, combinação linear).

    Args:
        N_sd_t (float): Força normal de tração solicitante de cálculo (N).
        M_sdx (float): Momento fletor solicitante de cálculo em torno de x (N.mm).
        M_sdy (float): Momento fletor solicitante de cálculo em torno de y (N.mm).
        A (float): Área da seção transversal (mm²).
        Wx (float): Módulo de resistência em relação a x (mm³).
        Wy (float): Módulo de resistência em relação a y (mm³).
        f_t0d (float): Resistência de cálculo à tração paralela (MPa).
        f_md (float): Resistência de cálculo à flexão (MPa).
        k_M (float): Coeficiente de correção para flexão (0.7 ou 1.0).

    Returns:
        tuple: (passou (bool), ratio_max (float))
    """
    if A <= TOL or Wx <= TOL or Wy <= TOL: return False, float('inf')
    if f_t0d <= TOL or f_md <= TOL: # Se alguma resistência é zero
        passa_sem_res = (abs(N_sd_t) < TOL and abs(M_sdx) < TOL and abs(M_sdy) < TOL)
        return passa_sem_res, 0.0

    # Termo da tração normalizada
    termo_N = abs(N_sd_t) / (A * f_t0d) if abs(A * f_t0d) > TOL else (float('inf') if abs(N_sd_t) > TOL else 0.0)

    # Termos da flexão normalizada
    sigma_Mx_d = abs(M_sdx) / Wx if Wx > TOL else (float('inf') if abs(M_sdx) > TOL else 0.0)
    sigma_My_d = abs(M_sdy) / Wy if Wy > TOL else (float('inf') if abs(M_sdy) > TOL else 0.0)
    termo_Mx = sigma_Mx_d / f_md if f_md > TOL else (float('inf') if sigma_Mx_d > TOL else 0.0)
    termo_My = sigma_My_d / f_md if f_md > TOL else (float('inf') if sigma_My_d > TOL else 0.0)

    # Condições de interação
    ratio1 = termo_N + termo_Mx + k_M * termo_My
    ratio2 = termo_N + k_M * termo_Mx + termo_My
    ratio_max = max(ratio1, ratio2)

    passou = ratio_max <= 1.0 + TOL
    return passou, ratio_max

# --- Funções de Estabilidade (Item 6.5 NBR 7190) ---
def calcular_indices_esbeltez(comprimento_L, Ke, raio_giracao_i, f_c0k, E_005):
    """
    Calcula o índice de esbeltez (lambda) e a esbeltez relativa (lambda_rel).
    Ref: NBR 7190-1:2022, Item 6.5.3 (Eq. 9) e Item 6.5.4 (Eq. 11, 12).

    Args:
        comprimento_L (float): Comprimento da peça (mm).
        Ke (float): Coeficiente de flambagem (adimensional).
        raio_giracao_i (float): Raio de giração da seção em relação ao eixo i (mm).
        f_c0k (float): Resistência característica à compressão paralela (MPa).
        E_005 (float): Módulo de elasticidade característico (5 percentil) (MPa).

    Returns:
        tuple: (lambda_i (float), lambda_rel_i (float))

    Raises:
        ValueError: Se inputs forem inválidos (e.g., raio_giracao_i <= 0).
    """
    if raio_giracao_i is None or raio_giracao_i <= TOL:
        raise ValueError(f"Raio de giração i ({raio_giracao_i}) deve ser positivo.")
    if E_005 is None or E_005 <= TOL:
        raise ValueError(f"Módulo de elasticidade E_005 ({E_005}) deve ser positivo.")
    if f_c0k is None or f_c0k <= TOL:
        raise ValueError(f"Resistência característica f_c0k ({f_c0k}) deve ser positiva.")
    if comprimento_L < 0 or Ke < 0:
        raise ValueError(f"Comprimento L ({comprimento_L}) e Ke ({Ke}) não podem ser negativos.")

    L0 = Ke * comprimento_L  # Comprimento de flambagem (Eq. 10 NBR7190)
    if L0 < TOL: # Se o comprimento de flambagem é zero, não há esbeltez
        return 0.0, 0.0

    lambda_i = L0 / raio_giracao_i # Índice de esbeltez (Eq. 9 NBR7190)

    # Esbeltez relativa (Eq. 11 e 12 NBR7190)
    termo_raiz_lambda_rel = f_c0k / E_005
    if termo_raiz_lambda_rel < 0: # Não deve ocorrer com inputs validados
        raise ValueError(f"Termo sob a raiz para lambda_rel (f_c0k/E_005 = {termo_raiz_lambda_rel:.2e}) é negativo.")

    lambda_rel_i = (lambda_i / math.pi) * math.sqrt(termo_raiz_lambda_rel)
    return lambda_i, lambda_rel_i

def calcular_coeficiente_reducao_kc(lambda_rel, beta_c=0.2):
    """
    Calcula o coeficiente de redução kc para estabilidade de peças comprimidas.
    Ref: NBR 7190-1:2022, Item 6.5.5, Eq. 14 e 15.

    Args:
        lambda_rel (float): Esbeltez relativa.
        beta_c (float, optional): Fator para peças estruturais (0.2 para madeira maciça/roliça,
                                  0.1 para MLC/MLCC/LVL). Default é 0.2.

    Returns:
        float: Coeficiente de redução kc (entre 0 e 1.0).

    Raises:
        ValueError: Se lambda_rel for None ou negativo.
    """
    if lambda_rel is None or lambda_rel < 0:
        raise ValueError(f"Esbeltez relativa lambda_rel ({lambda_rel}) inválida.")

    # Conforme Item 6.5.5, se lambda_rel <= 0.3, não há necessidade de verificação de estabilidade
    # (ou seja, kc seria considerado 1.0 para fins de cálculo da força resistente de estabilidade).
    if lambda_rel <= 0.3 + TOL:
        return 1.0

    # Cálculo de k_x ou k_y (Eq. 15)
    k_val = 0.5 * (1 + beta_c * (lambda_rel - 0.3) + lambda_rel**2)

    # Termo dentro da raiz quadrada na Eq. 14
    termo_raiz_quad = k_val**2 - lambda_rel**2

    # Trata caso de instabilidade numérica ou real onde termo_raiz_quad < 0
    if termo_raiz_quad < -TOL: # Usar uma pequena tolerância para erros de ponto flutuante
         print(f"AVISO NUMÉRICO: Termo sob a raiz quadrada (k² - λ_rel²) é negativo ({termo_raiz_quad:.2e}) para λ_rel={lambda_rel:.3f}, k_val={k_val:.3f}. Retornando kc próximo de zero, indicando instabilidade.")
         return TOL # Retorna um valor muito pequeno, efetivamente falhando na estabilidade
    elif termo_raiz_quad < 0: # Se for negativo mas muito próximo de zero
        termo_raiz_quad = 0 # Corrige para zero para evitar erro de math.domain

    # Denominador da Eq. 14
    denominador_kc = k_val + math.sqrt(termo_raiz_quad)

    if denominador_kc <= TOL:
        # Isso indica que a peça é extremamente esbelta e instável
        print(f"AVISO: Denominador no cálculo de kc é zero ou negativo ({denominador_kc:.2e}) para λ_rel={lambda_rel:.3f}. Peça instável.")
        return TOL # Retorna um valor muito pequeno

    kc = 1 / denominador_kc # Eq. 14
    return min(kc, 1.0) # Garante que kc não seja maior que 1.0

def verificar_compressao_axial_com_estabilidade(N_sd_c, A, f_c0k, f_c0d, E_005, comprimento_L, Ke_x=1.0, Ke_y=1.0, i_x=None, i_y=None, props_geom=None, beta_c=0.2):
    """
    Verifica ELU para compressão axial, incluindo resistência da seção e estabilidade.
    Ref: NBR 7190-1:2022, Itens 6.3.3 e 6.5.5.

    Args:
        N_sd_c (float): Força normal de compressão solicitante de cálculo (N).
        A (float): Área da seção (mm²).
        f_c0k (float): Resistência característica à compressão paralela (MPa).
        f_c0d (float): Resistência de cálculo à compressão paralela (MPa).
        E_005 (float): Módulo de elasticidade característico (MPa).
        comprimento_L (float): Comprimento da peça (mm).
        Ke_x (float, optional): Coef. de flambagem em torno de x. Default 1.0.
        Ke_y (float, optional): Coef. de flambagem em torno de y. Default 1.0.
        i_x (float, optional): Raio de giração em x (mm). Usado se props_geom não fornecido.
        i_y (float, optional): Raio de giração em y (mm). Usado se props_geom não fornecido.
        props_geom (dict, optional): Dicionário com 'i_x' e 'i_y'. Preferido sobre i_x, i_y diretos.
        beta_c (float, optional): Fator para kc. Default 0.2.

    Returns:
        tuple: (passou_geral, N_sd_c_abs,
                passou_resistencia, N_Rd_resistencia,
                passou_estabilidade_final, N_Rd_estabilidade,
                lambda_x, lambda_y, lambda_rel_x, lambda_rel_y,
                kc_x, kc_y,
                esbeltez_ok_limite_140, passou_estabilidade_forca_apenas)
    """
    N_sd_c_abs = abs(N_sd_c)
    if A is None or A <= TOL: raise ValueError(f"Área da seção A ({A}) inválida.")

    # 1. Verificação da Resistência da Seção (Item 6.3.3)
    if f_c0d is None or f_c0d <= TOL:
        passou_resistencia = N_sd_c_abs < TOL
        N_Rd_resistencia = 0.0
    else:
        N_Rd_resistencia = f_c0d * A
        passou_resistencia = N_sd_c_abs <= N_Rd_resistencia + TOL

    # Inicializa variáveis de estabilidade
    passou_estabilidade_forca_apenas = True # Se passa na verificação Nsd <= NRd,est (ignora lambda > 140)
    esbeltez_ok_limite_140 = True # Se lambda_max <= 140
    N_Rd_estabilidade = float('inf') # Se estabilidade não limitar (ex: lambda_rel <= 0.3)
    lambda_x, lambda_y = 0.0, 0.0
    lambda_rel_x, lambda_rel_y = 0.0, 0.0
    kc_x, kc_y = 1.0, 1.0

    # 2. Verificação da Estabilidade (Item 6.5.5) - Só é necessária se N_sd_c > 0 e f_c0d > 0
    if N_sd_c_abs > TOL and (f_c0d is not None and f_c0d > TOL):
        if E_005 is None or E_005 <= TOL: raise ValueError(f"E_005 ({E_005}) inválido para estabilidade.")
        if f_c0k is None or f_c0k <= TOL: raise ValueError(f"f_c0k ({f_c0k}) inválido para estabilidade.")

        # Determina raios de giração
        ix_calc = props_geom['i_x'] if props_geom and 'i_x' in props_geom else i_x
        iy_calc = props_geom['i_y'] if props_geom and 'i_y' in props_geom else i_y
        if ix_calc is None or iy_calc is None or ix_calc <= TOL or iy_calc <= TOL:
            raise ValueError(f"Raios de giração ix ({ix_calc}) ou iy ({iy_calc}) inválidos.")

        try:
            lambda_x, lambda_rel_x = calcular_indices_esbeltez(comprimento_L, Ke_x, ix_calc, f_c0k, E_005)
            lambda_y, lambda_rel_y = calcular_indices_esbeltez(comprimento_L, Ke_y, iy_calc, f_c0k, E_005)
        except ValueError as e:
             raise ValueError(f"Erro ao calcular índices de esbeltez para compressão: {e}") from e

        # Verifica se a estabilidade precisa ser considerada (lambda_rel > 0.3)
        if lambda_rel_x > 0.3 + TOL or lambda_rel_y > 0.3 + TOL:
            try:
                kc_x = calcular_coeficiente_reducao_kc(lambda_rel_x, beta_c)
                kc_y = calcular_coeficiente_reducao_kc(lambda_rel_y, beta_c)
            except ValueError as e:
                 raise ValueError(f"Erro ao calcular coeficientes kc para compressão: {e}") from e

            kc_min = min(kc_x, kc_y)
            N_Rd_estabilidade = kc_min * f_c0d * A
            passou_estabilidade_forca_apenas = N_sd_c_abs <= N_Rd_estabilidade + TOL
        # else: estabilidade não rege, N_Rd_estabilidade permanece infinito ou kc_min = 1.0

        # Verifica limite de esbeltez (Item 6.5.3, parte final)
        lambda_max = max(lambda_x, lambda_y)
        esbeltez_ok_limite_140 = lambda_max <= 140.0 + TOL
    # else: Se N_sd_c ou f_c0d é zero, não há compressão a verificar estabilidade

    passou_estabilidade_final = passou_estabilidade_forca_apenas and esbeltez_ok_limite_140
    passou_geral = passou_resistencia and passou_estabilidade_final

    return (
        passou_geral, N_sd_c_abs,
        passou_resistencia, N_Rd_resistencia,
        passou_estabilidade_final, N_Rd_estabilidade,
        lambda_x, lambda_y, lambda_rel_x, lambda_rel_y,
        kc_x, kc_y,
        esbeltez_ok_limite_140,
        passou_estabilidade_forca_apenas
    )

def verificar_flexocompressao_resistencia(N_sd_c, M_sdx, M_sdy, A, Wx, Wy, f_c0d, f_md, k_M):
    """
    Verifica a resistência da seção para flexocompressão (ELU).
    Ref: NBR 7190-1:2022, Item 6.3.7, Eq. (sem número, combinação quadrática e linear).

    Args:
        N_sd_c (float): Força normal de compressão solicitante de cálculo (N).
        M_sdx (float): Momento fletor solicitante em x (N.mm).
        M_sdy (float): Momento fletor solicitante em y (N.mm).
        A (float): Área da seção (mm²).
        Wx (float): Módulo de resistência em x (mm³).
        Wy (float): Módulo de resistência em y (mm³).
        f_c0d (float): Resistência de cálculo à compressão paralela (MPa).
        f_md (float): Resistência de cálculo à flexão (MPa).
        k_M (float): Coeficiente de correção para flexão.

    Returns:
        tuple: (passou (bool), ratio_max (float))
    """
    if A <= TOL or Wx <= TOL or Wy <= TOL: return False, float('inf')
    if f_c0d <= TOL or f_md <= TOL:
        passa_sem_res = (abs(N_sd_c) < TOL and abs(M_sdx) < TOL and abs(M_sdy) < TOL)
        return passa_sem_res, 0.0

    sigma_Ncd = abs(N_sd_c) / A
    sigma_Msdx = abs(M_sdx) / Wx
    sigma_Msdy = abs(M_sdy) / Wy

    # Termos da equação de interação (Item 6.3.7)
    termo_comp_quad = (sigma_Ncd / f_c0d)**2 if f_c0d > TOL else (float('inf') if sigma_Ncd > TOL else 0.0)
    termo_flex_x = sigma_Msdx / f_md if f_md > TOL else (float('inf') if sigma_Msdx > TOL else 0.0)
    termo_flex_y = sigma_Msdy / f_md if f_md > TOL else (float('inf') if sigma_Msdy > TOL else 0.0)

    ratio1 = termo_comp_quad + termo_flex_x + k_M * termo_flex_y
    ratio2 = termo_comp_quad + k_M * termo_flex_x + termo_flex_y
    ratio_max = max(ratio1, ratio2)

    passou = ratio_max <= 1.0 + TOL
    return passou, ratio_max

def verificar_flexocompressao_com_estabilidade(N_sd_c, M_sdx, M_sdy, A, Wx, Wy, f_c0k, f_c0d, f_md, E_005, comprimento_L, Ke_x, Ke_y, props_geom, beta_c, k_M):
    """
    Verifica a estabilidade para flexocompressão (ELU).
    Ref: NBR 7190-1:2022, Item 6.5.5, Eq. 13.
    Também verifica o limite de esbeltez lambda_max <= 140.

    Args:
        (Mesmos da flexocompressao_resistencia + E_005, comprimento_L, Ke_x, Ke_y, props_geom, beta_c)
        f_c0k (float): Resistência característica à compressão paralela (MPa).

    Returns:
        tuple: (passou_geral_estabilidade (bool), ratio_max_estabilidade (float),
                lambda_x, lambda_y, lambda_rel_x, lambda_rel_y, k_cx, k_cy,
                lambda_max_calculado, esbeltez_ok_limite_140, passou_ratio_estabilidade_apenas)
    """
    lambda_x_val, lambda_y_val = 0.0, 0.0
    lambda_rel_x_val, lambda_rel_y_val = 0.0, 0.0
    k_cx_val, k_cy_val = 1.0, 1.0
    ratio_max_est = 0.0
    lambda_max_calculado_val = 0.0
    esbeltez_ok = True
    passou_ratio_apenas = True # Assume que passa no ratio até ser calculado

    if A <= TOL or Wx <= TOL or Wy <= TOL:
        return False, float('inf'), 0,0,0,0,1,1, 0, False, False # Geometria inválida

    # Se não há esforços significativos ou resistências, considera como passou
    passa_sem_esforco_ou_resistencia = (abs(N_sd_c) < TOL and abs(M_sdx) < TOL and abs(M_sdy) < TOL) or \
                                       (f_c0d <= TOL or f_md <= TOL)
    if passa_sem_esforco_ou_resistencia:
        if (abs(N_sd_c) < TOL and abs(M_sdx) < TOL and abs(M_sdy) < TOL):
            return True, 0.0, 0,0,0,0,1,1, 0, True, True
        else: # resistências são zero mas esforços não
            return False, float('inf'), 0,0,0,0,1,1, 0, True, False


    # Calcula lambdas e kcs (mesmo se lambda_rel <= 0.3, para ter os valores)
    if props_geom:
        i_x_calc = props_geom.get('i_x')
        i_y_calc = props_geom.get('i_y')
    else:
        raise ValueError("props_geom (com i_x, i_y) são necessários para flexocompressão com estabilidade.")

    if i_x_calc is None or i_y_calc is None or i_x_calc <= TOL or i_y_calc <= TOL:
        raise ValueError(f"Raios de giração ix ({i_x_calc}) ou iy ({i_y_calc}) inválidos para estabilidade.")
    if E_005 is None or E_005 <= TOL: raise ValueError(f"E_005 ({E_005}) inválido.")
    if f_c0k is None or f_c0k <= TOL: raise ValueError(f"f_c0k ({f_c0k}) inválido.")

    try:
        lambda_x_val, lambda_rel_x_val = calcular_indices_esbeltez(comprimento_L, Ke_x, i_x_calc, f_c0k, E_005)
        lambda_y_val, lambda_rel_y_val = calcular_indices_esbeltez(comprimento_L, Ke_y, i_y_calc, f_c0k, E_005)
        k_cx_val = calcular_coeficiente_reducao_kc(lambda_rel_x_val, beta_c)
        k_cy_val = calcular_coeficiente_reducao_kc(lambda_rel_y_val, beta_c)
        lambda_max_calculado_val = max(lambda_x_val, lambda_y_val)
    except ValueError as e_stab:
        raise ValueError(f"Erro no cálculo dos parâmetros de estabilidade para flexocompressão: {e_stab}") from e_stab

    # 1. Verifica limite de esbeltez (lambda_max <= 140)
    esbeltez_ok = lambda_max_calculado_val <= 140.0 + TOL

    # 2. Calcula o ratio da estabilidade (Eq. 13)
    # Somente se lambda_rel_x > 0.3 ou lambda_rel_y > 0.3 (Item 6.5.5)
    # Se ambos <= 0.3, a estabilidade é considerada atendida em termos de redução de força (kc=1).
    # No entanto, as equações de interação ainda se aplicam com kc=1.
    sigma_Ncd = abs(N_sd_c) / A
    sigma_Msdx = abs(M_sdx) / Wx
    sigma_Msdy = abs(M_sdy) / Wy

    # Termos da equação de interação (Eq. 13)
    # Trata divisão por zero para kc*f_c0d ou f_md
    den_kcxfc0d = k_cx_val * f_c0d
    den_kcyfc0d = k_cy_val * f_c0d

    termo_N_kx = sigma_Ncd / den_kcxfc0d if abs(den_kcxfc0d) > TOL else (float('inf') if sigma_Ncd > TOL else 0.0)
    termo_N_ky = sigma_Ncd / den_kcyfc0d if abs(den_kcyfc0d) > TOL else (float('inf') if sigma_Ncd > TOL else 0.0)
    termo_Mx_fmd = sigma_Msdx / f_md if abs(f_md) > TOL else (float('inf') if sigma_Msdx > TOL else 0.0)
    termo_My_fmd = sigma_Msdy / f_md if abs(f_md) > TOL else (float('inf') if sigma_Msdy > TOL else 0.0)

    ratio1_est = termo_N_kx + termo_Mx_fmd + k_M * termo_My_fmd
    ratio2_est = termo_N_ky + k_M * termo_Mx_fmd + termo_My_fmd
    ratio_max_est = max(ratio1_est, ratio2_est)

    # 3. Verifica se o ratio de estabilidade passou (<= 1.0)
    passou_ratio_apenas = ratio_max_est <= 1.0 + TOL

    # 4. Resultado geral: passa apenas se esbeltez OK E ratio OK
    passou_geral_estabilidade = esbeltez_ok and passou_ratio_apenas

    return (passou_geral_estabilidade, ratio_max_est,
            lambda_x_val, lambda_y_val, lambda_rel_x_val, lambda_rel_y_val, k_cx_val, k_cy_val,
            lambda_max_calculado_val, esbeltez_ok, passou_ratio_apenas)

# --------------------------------------------------------------------------
# Verificar Dimensões Mínimas (Item 9.2.1 NBR 7190)
# --------------------------------------------------------------------------
def verificar_dimensoes_minimas(largura_b, altura_h, tipo_peca="principal_isolada"):
    """
    Verifica se a seção da peça atende às dimensões mínimas da NBR 7190-1:2022, Item 9.2.1.

    Args:
        largura_b (float): Largura da seção (mm).
        altura_h (float): Altura da seção (mm).
        tipo_peca (str, optional): Tipo da peça ('principal_isolada', 'secundaria_isolada',
                                   'principal_multipla', 'secundaria_multipla').
                                   Default é 'principal_isolada'.

    Returns:
        tuple: (area_ok (bool), espessura_ok (bool),
                area_requerida_mm2 (float), espessura_requerida_mm (float))

    Raises:
        ValueError: Se dimensões de entrada forem inválidas.
    """
    if largura_b <= TOL or altura_h <= TOL:
        raise ValueError(f"Dimensões b ({largura_b}) e h ({altura_h}) devem ser positivas.")

    area_calculada_mm2 = largura_b * altura_h
    espessura_calculada_min_mm = min(largura_b, altura_h)

    # Limites da NBR 7190-1:2022, Item 9.2.1
    # Valores em mm e mm² (convertidos de cm e cm²)
    if tipo_peca == "principal_isolada":
        area_requerida_mm2, espessura_requerida_mm = 5000, 50  # 50 cm², 5 cm
    elif tipo_peca == "secundaria_isolada":
        area_requerida_mm2, espessura_requerida_mm = 1800, 25  # 18 cm², 2.5 cm
    elif tipo_peca == "principal_multipla":
        area_requerida_mm2, espessura_requerida_mm = 3500, 25  # 35 cm², 2.5 cm
    elif tipo_peca == "secundaria_multipla":
        area_requerida_mm2, espessura_requerida_mm = 1800, 18  # 18 cm², 1.8 cm
    else:
        print(f"AVISO: Tipo de peça '{tipo_peca}' desconhecido para dimensões mínimas. "
              "Usando limites para 'principal_isolada'.")
        area_requerida_mm2, espessura_requerida_mm = 5000, 50

    area_ok = area_calculada_mm2 >= area_requerida_mm2 - TOL
    espessura_ok = espessura_calculada_min_mm >= espessura_requerida_mm - TOL

    return area_ok, espessura_ok, area_requerida_mm2, espessura_requerida_mm

# --------------------------------------------------------------------------
# Verificação de Estabilidade Lateral de Vigas (Item 6.5.6 NBR 7190)
# --------------------------------------------------------------------------
beta_M_tabela = { # Tabela 8 NBR 7190-1:2022 (gamma_f = 1.4, beta_E = 4)
    1: 6.0, 2: 8.8, 3: 12.3, 4: 15.9, 5: 19.5, 6: 23.1, 7: 26.7, 8: 30.3,
    9: 34.0, 10: 37.6, 11: 41.2, 12: 44.8, 13: 48.5, 14: 52.1, 15: 55.8,
    16: 59.4, 17: 63.0, 18: 66.7, 19: 70.3, 20: 74.0
}

def obter_beta_M(h_b_ratio):
    """
    Obtém o coeficiente beta_M da Tabela 8 da NBR 7190-1:2022 por interpolação linear.

    Args:
        h_b_ratio (float): Relação altura/largura (h/b) da viga.

    Returns:
        float or None: Valor de beta_M, ou None se h_b_ratio for inválido.
    """
    if h_b_ratio is None or not isinstance(h_b_ratio, (int, float)) or h_b_ratio <= TOL:
        print(f"AVISO: Relação h/b ({h_b_ratio}) inválida para obter beta_M. Retornando None.")
        return None

    # Trata limites da tabela
    if h_b_ratio < 1.0: return beta_M_tabela[1]
    if h_b_ratio >= 20.0: return beta_M_tabela[20] # Usa o valor de 20 se for maior ou igual

    h_b_inf = math.floor(h_b_ratio)
    h_b_sup = math.ceil(h_b_ratio)

    # Caso especial: h_b_ratio é exatamente um inteiro na tabela
    if abs(h_b_inf - h_b_ratio) < TOL and h_b_inf in beta_M_tabela:
        return beta_M_tabela[h_b_inf]
    # Caso raro: h_b_ratio coincide com o limite superior (ex: 3.000001)
    if abs(h_b_sup - h_b_ratio) < TOL and h_b_sup in beta_M_tabela:
         return beta_M_tabela[h_b_sup]

    beta_M_inf = beta_M_tabela.get(h_b_inf)
    beta_M_sup = beta_M_tabela.get(h_b_sup)

    if beta_M_inf is None or beta_M_sup is None:
        # Fallback se não encontrar os limites (improvável com os checks acima)
        # Tenta arredondar para o inteiro mais próximo e pegar da tabela
        rounded_h_b = round(h_b_ratio)
        beta_M_fallback = beta_M_tabela.get(rounded_h_b)
        print(f"AVISO: Não foi possível interpolar beta_M para h/b = {h_b_ratio:.2f}. "
              f"Usando valor para h/b arredondado para {rounded_h_b}: {beta_M_fallback}")
        return beta_M_fallback

    # Interpolação linear: beta_M = y1 + (y2 - y1) * (x - x1) / (x2 - x1)
    # Aqui: x = h_b_ratio, x1 = h_b_inf, x2 = h_b_sup (= h_b_inf + 1)
    #       y1 = beta_M_inf, y2 = beta_M_sup
    # Como x2 - x1 = 1, a fórmula simplifica
    beta_M_interpolado = beta_M_inf + (beta_M_sup - beta_M_inf) * (h_b_ratio - h_b_inf)
    return beta_M_interpolado

def verificar_estabilidade_lateral_viga(largura_b_mm, altura_h_mm, L1_mm, E0_med_MPa, f_md_MPa, k_mod, M_sdx_Nmm, Wx_mm3):
    """
    Verifica a estabilidade lateral de vigas retangulares conforme NBR 7190-1:2022, Item 6.5.6.

    Args:
        largura_b_mm (float): Largura da viga (mm).
        altura_h_mm (float): Altura da viga (mm).
        L1_mm (float): Distância entre pontos adjacentes da borda comprimida com
                       deslocamentos laterais impedidos (mm).
        E0_med_MPa (float): Módulo de elasticidade médio longitudinal (MPa).
        f_md_MPa (float): Resistência de cálculo à flexão (MPa).
        k_mod (float): Coeficiente de modificação total.
        M_sdx_Nmm (float): Momento fletor solicitante de cálculo em torno de x (N.mm).
        Wx_mm3 (float): Módulo de resistência da seção em torno de x (mm³).

    Returns:
        dict: Dicionário com resultados da verificação:
              {'verificacao_aplicavel', 'dispensado', 'passou', 'h_b_ratio', 'L1_b',
               'limite_dispensacao', 'beta_M', 'E0_ef', 'sigma_cd_atuante',
               'sigma_cd_max_adm', 'mensagem', 'erro'}
    """
    resultados = {
        'verificacao_aplicavel': False, 'dispensado': False, 'passou': None,
        'h_b_ratio': None, 'L1_b': None, 'limite_dispensacao': None,
        'beta_M': None, 'E0_ef': None, 'sigma_cd_atuante': None,
        'sigma_cd_max_adm': None, 'mensagem': '', 'erro': None
    }

    if abs(M_sdx_Nmm) < TOL: # Se não há momento significativo, não se aplica
        resultados['mensagem'] = "Não aplicável (Momento Msdx ≈ 0)."
        resultados['passou'] = True # Considera como "passou" pois não precisa verificar
        return resultados

    # Validação de entradas básicas
    inputs_invalidos_msg = []
    if largura_b_mm <= TOL: inputs_invalidos_msg.append("Largura (b) deve ser positiva.")
    if altura_h_mm <= TOL: inputs_invalidos_msg.append("Altura (h) deve ser positiva.")
    if L1_mm < 0: inputs_invalidos_msg.append("L1 não pode ser negativo.")
    # L1 pode ser zero se a viga for continuamente travada, mas a fórmula de dispensa fica indefinida.
    # A norma assume L1 > 0 para a condição de dispensa.
    if L1_mm <= TOL and abs(M_sdx_Nmm) > TOL : # Se L1 é zero mas há momento, é um problema para esta verificação
        inputs_invalidos_msg.append("L1 deve ser > 0 para verificar estabilidade lateral quando Msdx != 0.")
    if E0_med_MPa <= TOL: inputs_invalidos_msg.append("E0_med deve ser positivo.")
    if f_md_MPa <= TOL: inputs_invalidos_msg.append("f_md deve ser positivo.")
    if abs(k_mod) < TOL: inputs_invalidos_msg.append("k_mod não pode ser zero.")
    if Wx_mm3 <= TOL: inputs_invalidos_msg.append("Wx deve ser positivo.")

    if inputs_invalidos_msg:
        resultados['passou'] = False
        resultados['erro'] = f"Inputs inválidos para estabilidade lateral: {'; '.join(inputs_invalidos_msg)}"
        resultados['mensagem'] = resultados['erro']
        return resultados

    resultados['verificacao_aplicavel'] = True
    try:
        h_b_ratio = altura_h_mm / largura_b_mm
        resultados['h_b_ratio'] = h_b_ratio
        beta_M_val = obter_beta_M(h_b_ratio)
        if beta_M_val is None:
            raise ValueError(f"Não foi possível obter beta_M para h/b = {h_b_ratio:.2f}.")
        resultados['beta_M'] = beta_M_val

        # Calcula E0,ef (Item 5.8.7, Eq. 4)
        E0_ef_val = k_mod * E0_med_MPa
        resultados['E0_ef'] = E0_ef_val

        if L1_mm < TOL: # Se L1 for zero (ex: travamento contínuo)
            L1_b_val = 0.0
            limite_disp_val = float('inf') # Dispensado
            resultados['dispensado'] = True
            resultados['passou'] = True
            resultados['mensagem'] = f"Dispensado (L1 = {L1_mm:.0f} mm, indica travamento contínuo ou ausência de vão livre para flambagem lateral)."
        else:
            L1_b_val = L1_mm / largura_b_mm
            denominador_lim_disp = beta_M_val * f_md_MPa
            if abs(denominador_lim_disp) < TOL:
                # Se o denominador é zero, e E0_ef > 0, o limite é infinito (dispensado)
                # Se E0_ef também for zero, a situação é indeterminada, mas f_md já validado > 0
                limite_disp_val = float('inf') if E0_ef_val > TOL else 0.0
            else:
                limite_disp_val = E0_ef_val / denominador_lim_disp # Condição de dispensa (Eq. 17)

            # Verifica dispensa (Eq. 17)
            if L1_b_val <= limite_disp_val + TOL:
                resultados['dispensado'] = True
                resultados['passou'] = True
                resultados['mensagem'] = f"Dispensado (L1/b = {L1_b_val:.2f} <= Limite = {limite_disp_val:.2f})."
            else:
                # Verificação alternativa necessária (Eq. 18)
                resultados['dispensado'] = False
                sigma_cd_atuante_val = abs(M_sdx_Nmm) / Wx_mm3
                resultados['sigma_cd_atuante'] = sigma_cd_atuante_val

                denominador_sigma_adm = L1_b_val * beta_M_val
                if abs(denominador_sigma_adm) < TOL:
                    sigma_cd_max_adm_val = float('inf') if E0_ef_val > TOL else 0.0
                else:
                    sigma_cd_max_adm_val = E0_ef_val / denominador_sigma_adm
                resultados['sigma_cd_max_adm'] = sigma_cd_max_adm_val

                passou_alt = sigma_cd_atuante_val <= sigma_cd_max_adm_val + TOL
                resultados['passou'] = passou_alt
                if passou_alt:
                    resultados['mensagem'] = (f"Verificação alternativa OK "
                                              f"(σ_cd = {sigma_cd_atuante_val:.2f} MPa "
                                              f"<= σ_cd,adm = {sigma_cd_max_adm_val:.2f} MPa). "
                                              f"L1/b = {L1_b_val:.2f} > Lim.Disp. = {limite_disp_val:.2f}.")
                else:
                    resultados['mensagem'] = (f"Verificação alternativa NÃO OK "
                                              f"(σ_cd = {sigma_cd_atuante_val:.2f} MPa "
                                              f"> σ_cd,adm = {sigma_cd_max_adm_val:.2f} MPa). "
                                              f"L1/b = {L1_b_val:.2f} > Lim.Disp. = {limite_disp_val:.2f}.")
        resultados['L1_b'] = L1_b_val
        resultados['limite_dispensacao'] = limite_disp_val

    except (ValueError, KeyError, TypeError, ZeroDivisionError) as e:
        resultados['passou'] = False
        resultados['erro'] = f"Erro no cálculo de estabilidade lateral: {type(e).__name__} - {str(e)}"
        resultados['mensagem'] = resultados['erro']
        # traceback.print_exc() # Para debug do servidor
    except Exception as e_geral:
        resultados['passou'] = False
        resultados['erro'] = f"Erro inesperado na estabilidade lateral: {type(e_geral).__name__} - {str(e_geral)}"
        resultados['mensagem'] = resultados['erro']
        # traceback.print_exc()

    return resultados

# --------------------------------------------------------------------------
# Verificações ELS (Estado Limite de Serviço) - Flechas
# --------------------------------------------------------------------------

def calcular_flecha_instantanea_biapoiada_distribuida(q, L, E0_med, I):
    """
    Calcula a flecha instantânea MÁXIMA para viga biapoiada com carga distribuída q.
    Fórmula: delta = (5 * q * L^4) / (384 * E * I).
    Desconsidera deformação por cisalhamento por simplificação.

    Args:
        q (float): Carga distribuída (N/mm). (Positivo para baixo).
        L (float): Vão da viga (mm).
        E0_med (float): Módulo de elasticidade médio para ELS (MPa = N/mm²).
        I (float): Momento de inércia da seção em relação ao eixo de flexão (mm⁴).

    Returns:
        float: Flecha instantânea máxima (mm). Positiva se para baixo.
    """
    if E0_med is None or I is None or E0_med <= TOL or I <= TOL:
        print(f"AVISO FLECHA: E0_med ({E0_med}) ou I ({I}) inválidos para cálculo. Retornando 0.")
        return 0.0
    if L <= TOL: # Vão nulo, flecha nula
        return 0.0

    # Fórmula padrão da flecha máxima para viga biapoiada com carga distribuída
    delta = (5.0 * q * (L**4)) / (384.0 * E0_med * I)
    return delta

def obter_coeficiente_fluencia(classe_umidade, tipo_madeira="serrada"):
    """
    Retorna o coeficiente de fluência (phi) conforme Tabela 20 da NBR 7190-1:2022.

    Args:
        classe_umidade (str): Chave da classe de umidade (ex: 'classe_1').
        tipo_madeira (str, optional): Chave do tipo de madeira (ex: 'serrada', 'mlc').
                                     Default é 'serrada'.
    Returns:
        float: Coeficiente de fluência (phi).

    Raises:
        ValueError: Se a combinação de tipo de madeira e classe de umidade for inválida
                    ou não permitida pela Tabela 20.
    """
    if tipo_madeira not in kmod_fluencia_valores:
        # Se o tipo de madeira não está na tabela de fluência, tenta usar 'serrada' como fallback
        # ou levanta um erro mais específico se necessário no futuro.
        print(f"AVISO: Tipo de madeira '{tipo_madeira}' não encontrado na Tabela 20 para fluência. "
              "Usando valores para 'serrada' como fallback.")
        tipo_madeira_usar = "serrada"
    else:
        tipo_madeira_usar = tipo_madeira

    phi = kmod_fluencia_valores[tipo_madeira_usar].get(classe_umidade)

    if phi is None:
         # Caso onde a classe de umidade é válida mas a combinação não é permitida (ex: MLCC em Classe 4)
         if classe_umidade in kmod2_valores and kmod_fluencia_valores[tipo_madeira_usar].get(classe_umidade) is None:
              raise ValueError(f"Combinação de tipo de madeira '{tipo_madeira_usar}' e "
                               f"classe de umidade '{classe_umidade}' não é permitida para cálculo de fluência (Tabela 20).")
         else: # Caso onde a própria classe de umidade é inválida
              raise ValueError(f"Classe de umidade '{classe_umidade}' inválida para obter coeficiente de fluência.")
    return phi

def verificar_flecha_final(delta_inst_qp_x, delta_inst_qp_y, phi, L_mm, tipo_viga='biapoiada'):
    """
    Calcula a flecha final (considerando fluência) para combinação quase permanente
    e verifica contra o limite (L/250 para biapoiada, L/125 para balanço).
    Ref: NBR 7190-1:2022, Itens 8.1 (Eq. 23, 24) e 8.2 (Tabela 21, delta_net,fin).
    A contraflecha não está sendo considerada aqui (delta_camber = 0).
    Portanto, delta_final = delta_resultante_final_com_fluencia.

    Args:
        delta_inst_qp_x (float): Flecha instantânea em X para comb. quase permanente (mm).
        delta_inst_qp_y (float): Flecha instantânea em Y para comb. quase permanente (mm).
        phi (float): Coeficiente de fluência.
        L_mm (float): Vão da viga (mm).
        tipo_viga (str, optional): 'biapoiada' ou 'balanco'. Default 'biapoiada'.

    Returns:
        tuple: (passou_final, delta_x_final, delta_y_final, delta_resultante_final, delta_limite_final)
    """
    if L_mm <= TOL:
        return True, 0.0, 0.0, 0.0, float('inf') # Sem vão, sem flecha, passa.

    # Limite de flecha para delta_net,fin da Tabela 21
    if tipo_viga == 'biapoiada':
        # Usando o limite mais restritivo para delta_net,fin: L/350
        # Ou o mais comum L/250. O exercício usa L/250 para delta_fin.
        delta_limite_final = L_mm / 250.0
    elif tipo_viga == 'balanco':
        delta_limite_final = L_mm / 125.0 # Usando L/125
    else:
        print(f"AVISO FLECHA: Tipo de viga '{tipo_viga}' não reconhecido. Usando limite L/250.")
        delta_limite_final = L_mm / 250.0

    # Flecha final devido à carga quase permanente (incluindo fluência)
    # delta_fin,Gk = delta_inst,Gk * (1 + phi)
    # delta_fin,Qpk = delta_inst,Qpk,psi2 * (1 + phi)
    # Aqui, delta_inst_qp_x/y já é a flecha instantânea total da combinação quase permanente.
    delta_x_final_com_fluencia = delta_inst_qp_x * (1.0 + phi)
    delta_y_final_com_fluencia = delta_inst_qp_y * (1.0 + phi)

    # Flecha resultante final (vetorial)
    delta_resultante_final = math.sqrt(delta_x_final_com_fluencia**2 + delta_y_final_com_fluencia**2)

    # Verificação contra o limite (delta_net,fin = delta_resultante_final pois delta_camber = 0)
    passou_final = delta_resultante_final <= delta_limite_final + TOL

    return passou_final, delta_x_final_com_fluencia, delta_y_final_com_fluencia, delta_resultante_final, delta_limite_final

def verificar_flecha_instantanea_outra_comb(delta_inst_x, delta_inst_y, L_mm, tipo_viga='biapoiada'):
    """
    Verifica a flecha instantânea para uma combinação de ações (ex: vento)
    contra o limite L/300 (biapoiada) ou L/150 (balanço).
    Ref: NBR 7190-1:2022, Tabela 21 (para delta_inst).

    Args:
        delta_inst_x (float): Flecha instantânea em X para a combinação (mm).
        delta_inst_y (float): Flecha instantânea em Y para a combinação (mm).
        L_mm (float): Vão da viga (mm).
        tipo_viga (str, optional): 'biapoiada' ou 'balanco'. Default 'biapoiada'.

    Returns:
        tuple: (passou_inst (bool), delta_resultante_inst (float), delta_limite_inst (float))
    """
    if L_mm <= TOL:
        return True, 0.0, float('inf') # Sem vão, sem flecha, passa.

    # Limite de flecha para delta_inst da Tabela 21
    if tipo_viga == 'biapoiada':
        delta_limite_inst = L_mm / 300.0 # Limite mais comum para delta_inst
    elif tipo_viga == 'balanco':
        delta_limite_inst = L_mm / 150.0
    else:
        print(f"AVISO FLECHA INST: Tipo de viga '{tipo_viga}' não reconhecido. Usando limite L/300.")
        delta_limite_inst = L_mm / 300.0

    # Flecha resultante instantânea (vetorial)
    delta_resultante_inst = math.sqrt(delta_inst_x**2 + delta_inst_y**2)

    # Verificação
    passou_inst = abs(delta_resultante_inst) <= delta_limite_inst + TOL # Usa abs para considerar sucção

    return passou_inst, delta_resultante_inst, delta_limite_inst
