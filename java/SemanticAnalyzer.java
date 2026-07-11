import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.util.*;
import java.util.regex.*;

/**
 * Clase principal que realiza el análisis semántico de una secuencia de tokens
 * que representan instrucciones de una receta (ej. agregar ingredientes, mezclar).
 * Evalúa reglas de negocio específicas para asegurar que la receta sea coherente.
 */
public class SemanticAnalyzer {

    public static void main(String[] args) {
        // Almacena la entrada estándar en formato JSON que contiene los tokens generados por el analizador léxico.
        StringBuilder jsonInput = new StringBuilder();
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(System.in, "UTF-8"))) {
            String line;
            while ((line = reader.readLine()) != null) {
                jsonInput.append(line);
            }
        } catch (Exception e) {
            printErrorJson("Error leyendo la entrada estándar: " + e.getMessage());
            return;
        }

        // Convierte el JSON de entrada en una lista estructurada de tokens (representados como Mapas clave-valor).
        List<Map<String, String>> tokens = parseTokensJson(jsonInput.toString());
        
        // Bandera para rastrear si se ha incorporado algún ingrediente antes de intentar mezclar.
        boolean hasAddedAny = false;
        // Colecciones para registrar los resultados del análisis semántico.
        List<String> errors = new ArrayList<>();
        List<String> warnings = new ArrayList<>();
        List<String> ingredients = new ArrayList<>();

        // Recorre todos los tokens secuencialmente para aplicar las reglas de validación semántica.
        for (int i = 0; i < tokens.size(); i++) {
            Map<String, String> token = tokens.get(i);
            String type = token.get("type");
            String value = token.get("value");
            
            // Regla 1: Validar instrucciones de mezclado/batido.
            if ("INSTRUCCION_MEZCLAR".equals(type)) {
                // No se puede mezclar si no se ha agregado al menos un ingrediente previamente.
                if (!hasAddedAny) {
                    errors.add("Error Semántico: Se intenta mezclar/batir sin haber agregado ningún ingrediente primero.");
                }
                
                // Validar que el tiempo de mezclado sea lógico (debe estar expresado por el token NUMERO dentro de la misma instrucción).
                int j = i + 1;
                while (j < tokens.size()) {
                    Map<String, String> nextToken = tokens.get(j);
                    String nextType = nextToken.get("type");
                    if ("NUMERO".equals(nextType)) {
                        try {
                            int minutes = Integer.parseInt(nextToken.get("value"));
                            // El tiempo de mezclado debe estar en un rango razonable (1 a 120 minutos).
                            if (minutes <= 0 || minutes > 120) {
                                errors.add("Error Semántico: El tiempo de mezclado de " + minutes + " minutos no es válido. Debe ser entre 1 y 120 minutos.");
                            }
                        } catch (NumberFormatException e) {
                            errors.add("Error Semántico: El tiempo de mezclado '" + nextToken.get("value") + "' no es un número válido.");
                        }
                        break;
                    } else if ("CONECTOR_Y".equals(nextType) || "INSTRUCCION_INCORPORAR".equals(nextType) || "INSTRUCCION_MEZCLAR".equals(nextType)) {
                        break;
                    }
                    j++;
                }
            // Regla 2: Validar instrucciones de agregar/incorporar ingredientes.
            } else if ("INSTRUCCION_INCORPORAR".equals(type)) {
                // Marcamos que ya se ha agregado al menos un ingrediente.
                hasAddedAny = true;
                
                // Reconstruir el nombre del ingrediente acumulando los tokens UNKNOWN consecutivos
                // que aparecen después del verbo de incorporación.
                StringBuilder ingredientBuilder = new StringBuilder();
                int j = i + 1;
                while (j < tokens.size()) {
                    Map<String, String> nextToken = tokens.get(j);
                    String nextType = nextToken.get("type");
                    
                    // Detener la reconstrucción si encontramos un conector u otra instrucción principal.
                    if ("CONECTOR_Y".equals(nextType) || 
                        "INSTRUCCION_INCORPORAR".equals(nextType) || 
                        "INSTRUCCION_MEZCLAR".equals(nextType)) {
                        break;
                    }
                    
                    // Acumulamos el valor del token si es de tipo UNKNOWN (usualmente partes del nombre del ingrediente).
                    if ("UNKNOWN".equals(nextType)) {
                        if (ingredientBuilder.length() > 0) {
                            ingredientBuilder.append(" ");
                        }
                        ingredientBuilder.append(nextToken.get("value"));
                    }
                    j++;
                }
                
                String ingredient = ingredientBuilder.toString().trim();
                if (ingredient.isEmpty()) {
                    // Es un error si la instrucción de incorporar no tiene un ingrediente asociado.
                    errors.add("Error Semántico: La instrucción de agregar '" + value + "' no especifica qué ingrediente se está agregando (se esperaba un ingrediente, ej. 'harina').");
                } else {
                    String normalized = ingredient.toLowerCase();
                    // Emitir una advertencia si el ingrediente ya ha sido agregado antes en la receta.
                    if (ingredients.contains(normalized)) {
                        warnings.add("Advertencia Semántica: El ingrediente '" + ingredient + "' ha sido agregado más de una vez.");
                    }
                    ingredients.add(normalized);
                }
            }
        }

        // Determina si la receta es semánticamente válida (sin errores) y genera la salida JSON correspondiente.
        boolean valid = errors.isEmpty();
        printResultJson(valid, errors, warnings, ingredients);
    }

    /**
     * Parsea una cadena JSON que contiene una lista de objetos token sin requerir librerías externas.
     * Utiliza expresiones regulares para extraer los pares clave-valor de cada objeto JSON.
     * 
     * @param json Cadena de texto JSON con los tokens de entrada.
     * @return Una lista de mapas, donde cada mapa representa un token con sus atributos.
     */
    private static List<Map<String, String>> parseTokensJson(String json) {
        List<Map<String, String>> tokens = new ArrayList<>();
        // Expresión regular para encontrar llaves contenedoras de objetos JSON individuales: {}
        Pattern objectPattern = Pattern.compile("\\{[^{}]*\\}");
        Matcher objectMatcher = objectPattern.matcher(json);
        
        while (objectMatcher.find()) {
            String obj = objectMatcher.group();
            Map<String, String> token = new HashMap<>();
            
            // Expresión regular para extraer pares "clave" : "valor" o "clave" : número
            Pattern kvPattern = Pattern.compile("\"([^\"]+)\"\\s*:\\s*(?:\"([^\"]*)\"|(\\d+))");
            Matcher kvMatcher = kvPattern.matcher(obj);
            while (kvMatcher.find()) {
                String key = kvMatcher.group(1);
                // Si el valor capturado es numérico o de texto, lo asocia a su clave correspondiente.
                String val = kvMatcher.group(2) != null ? kvMatcher.group(2) : kvMatcher.group(3);
                token.put(key, val);
            }
            if (!token.isEmpty()) {
                tokens.add(token);
            }
        }
        return tokens;
    }

    /**
     * Imprime en la salida estándar la representación JSON del resultado del análisis semántico,
     * detallando el estado de validez, errores, advertencias e ingredientes encontrados.
     */
    private static void printResultJson(boolean valid, List<String> errors, List<String> warnings, List<String> ingredients) {
        StringBuilder sb = new StringBuilder();
        sb.append("{\n");
        sb.append("  \"valid\": ").append(valid).append(",\n");
        
        sb.append("  \"errors\": [\n");
        for (int i = 0; i < errors.size(); i++) {
            sb.append("    \"").append(escapeJson(errors.get(i))).append("\"");
            if (i < errors.size() - 1) sb.append(",");
            sb.append("\n");
        }
        sb.append("  ],\n");

        sb.append("  \"warnings\": [\n");
        for (int i = 0; i < warnings.size(); i++) {
            sb.append("    \"").append(escapeJson(warnings.get(i))).append("\"");
            if (i < warnings.size() - 1) sb.append(",");
            sb.append("\n");
        }
        sb.append("  ],\n");

        sb.append("  \"ingredients\": [\n");
        for (int i = 0; i < ingredients.size(); i++) {
            sb.append("    \"").append(escapeJson(ingredients.get(i))).append("\"");
            if (i < ingredients.size() - 1) sb.append(",");
            sb.append("\n");
        }
        sb.append("  ]\n");
        sb.append("}");
        System.out.println(sb.toString());
    }

    /**
     * Imprime una estructura JSON estándar que representa un fallo crítico en la ejecución del analizador
     * (por ejemplo, fallos de lectura de la entrada estándar).
     */
    private static void printErrorJson(String errMsg) {
        System.out.println("{\n  \"valid\": false,\n  \"errors\": [\"" + escapeJson(errMsg) + "\"],\n  \"warnings\": [],\n  \"ingredients\": []\n}");
    }

    /**
     * Escapa caracteres especiales (como comillas, barras invertidas y saltos de línea)
     * para asegurar que las cadenas generadas sean JSON válidos.
     */
    private static String escapeJson(String str) {
        if (str == null) return "";
        return str.replace("\\", "\\\\")
                  .replace("\"", "\\\"")
                  .replace("\b", "\\b")
                  .replace("\f", "\\f")
                  .replace("\n", "\\n")
                  .replace("\r", "\\r")
                  .replace("\t", "\\t");
    }
}
