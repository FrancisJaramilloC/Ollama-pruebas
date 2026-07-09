import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.util.*;
import java.util.regex.*;

public class SemanticAnalyzer {

    public static void main(String[] args) {
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

        List<Map<String, String>> tokens = parseTokensJson(jsonInput.toString());
        
        boolean hasAddedAny = false;
        List<String> errors = new ArrayList<>();
        List<String> warnings = new ArrayList<>();
        List<String> ingredients = new ArrayList<>();

        for (int i = 0; i < tokens.size(); i++) {
            Map<String, String> token = tokens.get(i);
            String type = token.get("type");
            String value = token.get("value");
            
            if ("INSTRUCCION_MEZCLAR".equals(type)) {
                if (!hasAddedAny) {
                    errors.add("Error Semántico: Se intenta mezclar/batir sin haber agregado ningún ingrediente primero.");
                }
                
                // Buscar el número de tiempo de mezclado que sigue
                if (i + 1 < tokens.size()) {
                    Map<String, String> nextToken = tokens.get(i + 1);
                    if ("NUMERO".equals(nextToken.get("type"))) {
                        try {
                            int minutes = Integer.parseInt(nextToken.get("value"));
                            if (minutes <= 0 || minutes > 120) {
                                errors.add("Error Semántico: El tiempo de mezclado de " + minutes + " minutos no es válido. Debe ser entre 1 y 120 minutos.");
                            }
                        } catch (NumberFormatException e) {
                            errors.add("Error Semántico: El tiempo de mezclado '" + nextToken.get("value") + "' no es un número válido.");
                        }
                    }
                }
            } else if ("INSTRUCCION_INCORPORAR".equals(type)) {
                hasAddedAny = true;
                
                // Encontrar el ingrediente (reunir todos los tokens UNKNOWN después de la cantidad)
                StringBuilder ingredientBuilder = new StringBuilder();
                int j = i + 1;
                while (j < tokens.size()) {
                    Map<String, String> nextToken = tokens.get(j);
                    String nextType = nextToken.get("type");
                    
                    // Si encontramos un conector u otra instrucción, paramos
                    if ("CONECTOR_Y".equals(nextType) || 
                        "INSTRUCCION_INCORPORAR".equals(nextType) || 
                        "INSTRUCCION_MEZCLAR".equals(nextType)) {
                        break;
                    }
                    
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
                    errors.add("Error Semántico: La instrucción de agregar '" + value + "' no especifica qué ingrediente se está agregando (se esperaba un ingrediente, ej. 'harina').");
                } else {
                    String normalized = ingredient.toLowerCase();
                    if (ingredients.contains(normalized)) {
                        warnings.add("Advertencia Semántica: El ingrediente '" + ingredient + "' ha sido agregado más de una vez.");
                    }
                    ingredients.add(normalized);
                }
            }
        }

        // Generar respuesta JSON
        boolean valid = errors.isEmpty();
        printResultJson(valid, errors, warnings, ingredients);
    }

    private static List<Map<String, String>> parseTokensJson(String json) {
        List<Map<String, String>> tokens = new ArrayList<>();
        // Encontrar objetos JSON del tipo {"type": "...", "value": "...", "origin": "..."}
        Pattern objectPattern = Pattern.compile("\\{[^{}]*\\}");
        Matcher objectMatcher = objectPattern.matcher(json);
        
        while (objectMatcher.find()) {
            String obj = objectMatcher.group();
            Map<String, String> token = new HashMap<>();
            
            // Extraer pares clave-valor
            Pattern kvPattern = Pattern.compile("\"([^\"]+)\"\\s*:\\s*(?:\"([^\"]*)\"|(\\d+))");
            Matcher kvMatcher = kvPattern.matcher(obj);
            while (kvMatcher.find()) {
                String key = kvMatcher.group(1);
                String val = kvMatcher.group(2) != null ? kvMatcher.group(2) : kvMatcher.group(3);
                token.put(key, val);
            }
            if (!token.isEmpty()) {
                tokens.add(token);
            }
        }
        return tokens;
    }

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

    private static void printErrorJson(String errMsg) {
        System.out.println("{\n  \"valid\": false,\n  \"errors\": [\"" + escapeJson(errMsg) + "\"],\n  \"warnings\": [],\n  \"ingredients\": []\n}");
    }

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
