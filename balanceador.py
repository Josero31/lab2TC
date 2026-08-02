"""
Balanceador de expresiones infix usando una pila (Stack).

El programa:
  1. Lee un archivo de texto (una expresión por línea).
  2. Para cada línea, recorre carácter por carácter usando una pila
     para llevar registro de los símbolos de apertura: ( [ {
  3. Indica si la expresión está bien balanceada o no.
  4. Muestra la secuencia de pasos de la pila (push/pop) para cada símbolo
     de interés procesado, de forma que se pueda validar el algoritmo.

Símbolos de interés considerados: ( ) [ ] { }
(fácilmente ampliable agregando pares al diccionario PARES)

Uso:
    python balanceador.py archivo.txt
"""

import sys


# Mapeo de símbolo de cierre -> símbolo de apertura correspondiente
PARES = {
    ')': '(',
    ']': '[',
    '}': '{',
}
APERTURAS = set(PARES.values())
CIERRES = set(PARES.keys())


class Pila:
    """Implementación explícita de una pila (LIFO) usando una lista de Python."""

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
        # Representación de la pila de abajo hacia arriba: [ fondo ... tope ]
        return '[' + ' '.join(self._datos) + ']' if self._datos else '[]'


def balancear_expresion(expresion):
    """
    Recorre la expresión y valida el balanceo de símbolos usando una pila.

    Retorna una tupla:
        (es_balanceada: bool, pasos: list[str], motivo: str)

    'pasos' contiene una línea de texto por cada operación relevante sobre
    la pila (push de apertura, pop al encontrar cierre, o error detectado),
    para poder mostrar la traza completa del algoritmo.
    """
    pila = Pila()
    pasos = []
    motivo = "Balanceada correctamente."

    for indice, caracter in enumerate(expresion):
        if caracter in APERTURAS:
            pila.push(caracter)
            pasos.append(
                f"  pos {indice:>3} | '{caracter}' -> PUSH   | pila: {pila}"
            )

        elif caracter in CIERRES:
            si_estaba_vacia = pila.esta_vacia()
            if si_estaba_vacia:
                pasos.append(
                    f"  pos {indice:>3} | '{caracter}' -> POP   | ERROR: pila vacía, "
                    f"no hay apertura para cerrar con '{caracter}'"
                )
                motivo = (
                    f"Símbolo de cierre '{caracter}' en la posición {indice} "
                    f"no tiene apertura correspondiente."
                )
                return False, pasos, motivo

            tope = pila.peek()
            apertura_esperada = PARES[caracter]

            if tope == apertura_esperada:
                pila.pop()
                pasos.append(
                    f"  pos {indice:>3} | '{caracter}' -> POP    | coincide con '{tope}' "
                    f"| pila: {pila}"
                )
            else:
                pasos.append(
                    f"  pos {indice:>3} | '{caracter}' -> POP   | ERROR: se esperaba cerrar "
                    f"'{tope}' pero llegó '{caracter}'"
                )
                motivo = (
                    f"Símbolo '{caracter}' en la posición {indice} no coincide "
                    f"con el símbolo abierto más reciente ('{tope}')."
                )
                return False, pasos, motivo
        # cualquier otro carácter (letras, dígitos, operadores, '.', '|', etc.)
        # no es un símbolo de interés y se ignora para efectos de la pila

    if not pila.esta_vacia():
        pendientes = ', '.join(f"'{s}'" for s in pila._datos)
        motivo = f"Quedaron símbolos sin cerrar al final de la expresión: {pendientes}."
        return False, pasos, motivo

    return True, pasos, motivo


def procesar_archivo(ruta_archivo):
    """Lee el archivo línea por línea y ejecuta el algoritmo sobre cada una."""
    try:
        with open(ruta_archivo, 'r', encoding='utf-8') as archivo:
            lineas = [linea.rstrip('\n') for linea in archivo]
    except FileNotFoundError:
        print(f"ERROR: no se encontró el archivo '{ruta_archivo}'.")
        sys.exit(1)

    print(f"Archivo a procesar: {ruta_archivo}")
    print(f"Total de líneas encontradas: {len(lineas)}")
    print("=" * 70)

    for numero_linea, expresion in enumerate(lineas, start=1):
        if expresion.strip() == "":
            continue  # se ignoran líneas en blanco

        print(f"\nLínea {numero_linea}: {expresion}")
        print("-" * 70)

        balanceada, pasos, motivo = balancear_expresion(expresion)

        if pasos:
            print("Secuencia de pasos de la pila:")
            for paso in pasos:
                print(paso)
        else:
            print("  (No se encontraron símbolos de interés '()[]{}' en la línea)")

        resultado = "BALANCEADA ✔" if balanceada else "NO BALANCEADA ✘"
        print(f"\nResultado: {resultado}")
        print(f"Detalle:   {motivo}")
        print("=" * 70)


def main():
    if len(sys.argv) != 2:
        print("Uso: python balanceador.py <ruta_del_archivo.txt>")
        sys.exit(1)

    procesar_archivo(sys.argv[1])


if __name__ == "__main__":
    main()
