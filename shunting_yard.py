"""
Shunting Yard aplicado a expresiones regulares: convierte de infix a postfix.

El programa:
  1. Lee un archivo de texto (una expresión regular por línea).
  2. Tokeniza cada expresión reconociendo:
       - literales normales (letras, dígitos, el comodín '.')
       - caracteres escapados con '\' (verificando que el escape sea válido)
       - clases de caracteres '[...]' como un solo operando atómico
       - cuantificadores '{n,m}' como operador postfijo
       - operadores '|' (alternancia), '*' '+' '?' (repetición) y '(' ')'
  3. Convierte las extensiones '+' y '?' a operadores básicos:
       - a+  ->  a a*      (concatenación de a con a*)
       - a?  ->  (a|ε)     (alternancia de a con la cadena vacía)
     El operando puede ser un solo átomo o un grupo completo entre paréntesis.
  4. Inserta el operador de concatenación implícito donde corresponde.
  5. Aplica el algoritmo de Shunting Yard para producir la expresión en
     notación postfix, mostrando la pila y la salida en cada paso.

Uso:
    python shunting_yard.py archivo.txt
"""

import sys


# ---------------------------------------------------------------------------
# Tipos de token
# ---------------------------------------------------------------------------
LITERAL = "LITERAL"
LPAREN = "LPAREN"
RPAREN = "RPAREN"
ALT = "ALT"          # |
CONCAT = "CONCAT"    # operador implícito de concatenación
QUANT = "QUANT"       # * + ? {n,m}


class Token:
    def __init__(self, tipo, valor):
        self.tipo = tipo
        self.valor = valor  # texto original del token, para mostrarlo

    def __repr__(self):
        return self.valor

    def __eq__(self, otro):
        return isinstance(otro, Token) and self.tipo == otro.tipo and self.valor == otro.valor


# precedencia de operadores (mayor número = mayor precedencia)
PRECEDENCIA = {
    ALT: 1,
    CONCAT: 2,
    QUANT: 3,
}


class Pila:
    """Pila (LIFO) explícita usada por el algoritmo."""

    def __init__(self):
        self._datos = []

    def push(self, elemento):
        self._datos.append(elemento)

    def pop(self):
        return self._datos.pop()

    def peek(self):
        return self._datos[-1]

    def esta_vacia(self):
        return len(self._datos) == 0

    def __str__(self):
        return "[" + " ".join(str(t) for t in self._datos) + "]" if self._datos else "[]"


class ErrorExpresion(Exception):
    pass


# ---------------------------------------------------------------------------
# Tokenización
# ---------------------------------------------------------------------------
def tokenizar(expresion):
    """
    Convierte el string de la expresión en una lista de Token.
    Reconoce escapes '\\x', clases de caracteres '[...]' y cuantificadores
    '{n,m}' como tokens atómicos. Lanza ErrorExpresion si encuentra un
    escape inválido o una clase/cuantificador sin cerrar.
    """
    # los espacios son solo de formato/lectura, no forman parte de la sintaxis
    expresion = "".join(expresion.split(" "))

    tokens = []
    i = 0
    n = len(expresion)

    while i < n:
        c = expresion[i]

        if c == "\\":
            # verificador de caracteres escapados
            if i + 1 >= n:
                raise ErrorExpresion(
                    f"Escape inválido: '\\' al final de la expresión (posición {i})."
                )
            escapado = expresion[i:i + 2]  # ej: "\+"
            tokens.append(Token(LITERAL, escapado))
            i += 2

        elif c == "[":
            cierre = expresion.find("]", i + 1)
            if cierre == -1:
                raise ErrorExpresion(
                    f"Clase de caracteres sin cerrar: falta ']' (abre en posición {i})."
                )
            tokens.append(Token(LITERAL, expresion[i:cierre + 1]))
            i = cierre + 1

        elif c == "{":
            cierre = expresion.find("}", i + 1)
            if cierre == -1:
                raise ErrorExpresion(
                    f"Cuantificador sin cerrar: falta '}}' (abre en posición {i})."
                )
            tokens.append(Token(QUANT, expresion[i:cierre + 1]))
            i = cierre + 1

        elif c == "(":
            tokens.append(Token(LPAREN, c))
            i += 1

        elif c == ")":
            tokens.append(Token(RPAREN, c))
            i += 1

        elif c == "|":
            tokens.append(Token(ALT, c))
            i += 1

        elif c in ("*", "+", "?"):
            tokens.append(Token(QUANT, c))
            i += 1

        else:
            # cualquier otro carácter (letras, dígitos, '.', etc.) es literal
            tokens.append(Token(LITERAL, c))
            i += 1

    return tokens


def _span_operando(tokens, indice_operador):
    """
    Dado el índice de un operador postfijo ('+' o '?'), localiza el rango
    [inicio, fin] del operando inmediatamente anterior: un solo átomo
    (LITERAL) o un grupo completo entre paréntesis '(...)'.
    Lanza ErrorExpresion si no hay un operando válido antes del operador.
    """
    if indice_operador == 0:
        raise ErrorExpresion(
            f"El operador '{tokens[indice_operador].valor}' no tiene un operando antes (inicio de la expresión)."
        )

    anterior = tokens[indice_operador - 1]

    if anterior.tipo == RPAREN:
        profundidad = 0
        j = indice_operador - 1
        while j >= 0:
            if tokens[j].tipo == RPAREN:
                profundidad += 1
            elif tokens[j].tipo == LPAREN:
                profundidad -= 1
                if profundidad == 0:
                    return j, indice_operador - 1
            j -= 1
        raise ErrorExpresion(
            f"Paréntesis de cierre sin apertura correspondiente antes de "
            f"'{tokens[indice_operador].valor}'."
        )

    if anterior.tipo == LITERAL:
        return indice_operador - 1, indice_operador - 1

    raise ErrorExpresion(
        f"El operador '{tokens[indice_operador].valor}' en la posición {indice_operador} "
        f"no tiene un operando válido (literal o grupo entre paréntesis) inmediatamente antes."
    )


def expandir_extensiones(tokens):
    """
    Convierte las extensiones '+' y '?' a operadores básicos (concatenación,
    alternancia y '*'), reescribiendo el flujo de tokens ANTES de correr el
    Shunting Yard:
        operando+  ->  operando operando *
        operando?  ->  ( operando | ε )

    Se repite hasta que no queden '+' ni '?' en la expresión, de modo que
    los casos anidados (p. ej. "(a+)?") se expandan de adentro hacia afuera.

    Retorna (tokens_expandidos, pasos) donde 'pasos' describe cada
    conversión realizada, para poder mostrarla en la traza del programa.
    """
    tokens = list(tokens)
    pasos = []
    hubo_cambio = True

    while hubo_cambio:
        hubo_cambio = False
        for indice, token in enumerate(tokens):
            if token.tipo != QUANT or token.valor not in ("+", "?"):
                continue

            inicio, fin = _span_operando(tokens, indice)
            operando = tokens[inicio:fin + 1]
            operando_str = "".join(str(t) for t in operando)

            if token.valor == "+":
                expansion = list(operando) + list(operando) + [Token(QUANT, "*")]
                pasos.append(
                    f"'{operando_str}+' -> se expande a "
                    f"'{operando_str}{operando_str}*'  (a+ = a·a*)"
                )
            else:  # '?'
                expansion = (
                    [Token(LPAREN, "(")]
                    + list(operando)
                    + [Token(ALT, "|"), Token(LITERAL, "ε"), Token(RPAREN, ")")]
                )
                pasos.append(
                    f"'{operando_str}?' -> se expande a "
                    f"'({operando_str}|ε)'  (a? = (a|ε))"
                )

            tokens = tokens[:inicio] + expansion + tokens[indice + 1:]
            hubo_cambio = True
            break  # se reinicia el recorrido sobre la lista ya modificada

    return tokens, pasos


def insertar_concatenacion(tokens):
    """
    Inserta tokens CONCAT explícitos donde la concatenación es implícita.
    Regla: se inserta concatenación entre el token A y el token B si
    A puede terminar un operando (LITERAL, RPAREN, QUANT) y
    B puede empezar un operando (LITERAL, LPAREN).
    """
    if not tokens:
        return tokens

    resultado = [tokens[0]]
    for anterior, actual in zip(tokens, tokens[1:]):
        termina_operando = anterior.tipo in (LITERAL, RPAREN, QUANT)
        empieza_operando = actual.tipo in (LITERAL, LPAREN)
        if termina_operando and empieza_operando:
            resultado.append(Token(CONCAT, "·"))
        resultado.append(actual)
    return resultado


# ---------------------------------------------------------------------------
# Shunting Yard
# ---------------------------------------------------------------------------
def a_postfix(expresion):
    """
    Ejecuta el algoritmo de Shunting Yard sobre la expresión dada.
    Retorna (postfix_tokens, pasos_expansion, pasos_shunting):
      - pasos_expansion: traza de las conversiones de '+' y '?' a
        operadores básicos, realizadas antes del Shunting Yard.
      - pasos_shunting: traza de cada operación sobre la pila y la salida.
    Lanza ErrorExpresion si la tokenización o el balanceo de paréntesis falla.
    """
    tokens_crudos = tokenizar(expresion)
    tokens_expandidos, pasos_expansion = expandir_extensiones(tokens_crudos)
    tokens = insertar_concatenacion(tokens_expandidos)

    pila = Pila()
    salida = []
    pasos = []

    def snapshot(accion):
        salida_str = " ".join(str(t) for t in salida) if salida else "(vacía)"
        pasos.append(f"  {accion:<28} | pila: {pila} | salida: {salida_str}")

    for token in tokens:
        if token.tipo == LITERAL:
            salida.append(token)
            snapshot(f"'{token.valor}' -> operando, a salida")

        elif token.tipo == LPAREN:
            pila.push(token)
            snapshot(f"'{token.valor}' -> PUSH '('")

        elif token.tipo == RPAREN:
            snapshot(f"'{token.valor}' -> POP hasta '('")
            encontro_apertura = False
            while not pila.esta_vacia():
                tope = pila.pop()
                if tope.tipo == LPAREN:
                    encontro_apertura = True
                    break
                salida.append(tope)
            if not encontro_apertura:
                raise ErrorExpresion("Paréntesis de cierre ')' sin apertura correspondiente.")
            snapshot("   ... descartado '('")

        else:  # ALT, CONCAT o QUANT: operador
            while (not pila.esta_vacia()
                   and pila.peek().tipo in PRECEDENCIA
                   and PRECEDENCIA[pila.peek().tipo] >= PRECEDENCIA[token.tipo]):
                salida.append(pila.pop())
            pila.push(token)
            snapshot(f"'{token.valor}' -> PUSH operador (precedencia {PRECEDENCIA[token.tipo]})")

    # vaciar la pila al final
    while not pila.esta_vacia():
        tope = pila.pop()
        if tope.tipo in (LPAREN, RPAREN):
            raise ErrorExpresion("Paréntesis de apertura '(' sin cierre correspondiente.")
        salida.append(tope)
        snapshot(f"fin de expresión -> POP '{tope.valor}' a salida")

    return salida, pasos_expansion, pasos


# ---------------------------------------------------------------------------
# Procesamiento de archivo
# ---------------------------------------------------------------------------
def procesar_archivo(ruta_archivo):
    try:
        with open(ruta_archivo, "r", encoding="utf-8") as archivo:
            lineas = [linea.rstrip("\n") for linea in archivo]
    except FileNotFoundError:
        print(f"ERROR: no se encontró el archivo '{ruta_archivo}'.")
        sys.exit(1)

    print(f"Archivo a procesar: {ruta_archivo}")
    print(f"Total de líneas encontradas: {len(lineas)}")
    print("=" * 70)

    for numero_linea, expresion in enumerate(lineas, start=1):
        if expresion.strip() == "":
            continue

        print(f"\nLínea {numero_linea} (infix): {expresion}")
        print("-" * 70)

        try:
            postfix_tokens, pasos_expansion, pasos_shunting = a_postfix(expresion)
        except ErrorExpresion as error:
            print(f"  ERROR: {error}")
            print("=" * 70)
            continue

        if pasos_expansion:
            print("Conversión de extensiones '+' y '?' a operadores básicos:")
            for paso in pasos_expansion:
                print(f"  {paso}")
        else:
            print("  (No se encontraron operadores '+' o '?' que convertir)")
        print()

        print("Pasos del algoritmo de Shunting Yard:")
        for paso in pasos_shunting:
            print(paso)

        postfix_str = " ".join(str(t) for t in postfix_tokens)
        print(f"\nResultado (postfix): {postfix_str}")
        print("=" * 70)


def main():
    if len(sys.argv) != 2:
        print("Uso: python shunting_yard.py <ruta_del_archivo.txt>")
        sys.exit(1)
    procesar_archivo(sys.argv[1])


if __name__ == "__main__":
    main()
