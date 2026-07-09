# Compilador de Recetas de Cocina (DSL)

Este proyecto es un compilador para un lenguaje de dominio especifico (DSL) de recetas de cocina, estructurado bajo la arquitectura Modelo-Vista-Controlador (MVC) utilizando Flask para la interfaz y Java para la validacion semantica.

## Funcionamiento del Compilador

El proceso de compilacion de una receta se realiza en las siguientes fases:

1. Analisis lexico (Fase 1): Se ejecuta en Python de forma concurrente mediante un ThreadPoolExecutor. El escaner separa tokens duros (NUMERO, CONECTOR_Y) usando expresiones regulares clasificados por el AFD en el hilo principal, mientras envia fragmentos no reconocidos al LLM (Ollama) en hilos separados para clasificarlos como INSTRUCCION_INCORPORAR, CANTIDAD o INSTRUCCION_MEZCLAR.
2. Analisis sintactico (Fase 2): El parser en Python valida la secuencia de tokens frente a las reglas BNF. Si es valida, genera un arbol de sintaxis abstracta (AST).
3. Analisis semantico (Fase 3): Si la sintaxis es valida, el modulo Python invoca al analizador semantico en Java 21 a traves de un subproceso, enviando la lista de tokens en formato JSON por la entrada estandar.
4. Visualizacion del AST (Vista): La interfaz de Flask dibuja el arbol de sintaxis utilizando elementos HTML/CSS con lineas conectoras para representar la jerarquia de las instrucciones.

### Reglas Semanticas Validadas en Java

- Se prohibe iniciar la receta con una accion de mezclado sin haber agregado ingredientes previamente.
- Toda accion de agregar debe indicar especificamente un ingrediente despues de la cantidad.
- Los tiempos de mezclado indicados deben estar en el rango de 1 a 120 minutos.
- Se genera una advertencia si el mismo ingrediente es incorporado mas de una vez.

## Requisitos

- Python 3.10+
- JDK 21
- Ollama corriendo en http://localhost:11434 con el modelo llama3.2:3b

## Instalacion y Preparacion

1. Instalar las dependencias de Python en el entorno virtual:
   ```bash
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Compilar el analizador semantico en Java:
   ```bash
   javac java/SemanticAnalyzer.java
   ```

## Ejecucion

1. Iniciar el servidor web de Flask en el puerto 8000:
   ```bash
   python server.py
   ```

2. Abrir el navegador e ingresar a la interfaz:
   ```
   http://localhost:8000
   ```
