document.addEventListener("DOMContentLoaded", () => {
    const recipeInput = document.getElementById("recipe-input");
    const charCounter = document.getElementById("char-counter");
    const btnCompile = document.getElementById("btn-compile");
    const presetButtons = document.querySelectorAll(".btn-preset");
    
    const placeholderResult = document.getElementById("placeholder-result");
    const loader = document.getElementById("loader");
    const compilationResults = document.getElementById("compilation-results");
    
    // Result sections
    const tokenList = document.getElementById("token-list");
    const syntaxStatusBadge = document.getElementById("syntax-status-badge");
    const syntaxDetails = document.getElementById("syntax-details");
    
    const semanticStatusBadge = document.getElementById("semantic-status-badge");
    const semanticDetails = document.getElementById("semantic-details");
    const detectedIngredientsContainer = document.getElementById("detected-ingredients-container");
    const ingredientsTags = document.getElementById("ingredients-tags");
    
    const astTree = document.getElementById("ast-tree");

    // 1. Character Counter
    recipeInput.addEventListener("input", () => {
        const length = recipeInput.value.length;
        charCounter.textContent = `${length} ${length === 1 ? 'caracter' : 'caracteres'}`;
    });

    // 2. Preset Code Loading
    presetButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            const code = btn.getAttribute("data-code");
            recipeInput.value = code;
            recipeInput.dispatchEvent(new Event("input"));
            recipeInput.focus();
        });
    });

    // 3. Compile Request
    btnCompile.addEventListener("click", async () => {
        const sourceCode = recipeInput.value.trim();
        if (!sourceCode) {
            alert("Por favor escribe una receta antes de compilar.");
            return;
        }

        // Show loading state
        placeholderResult.classList.add("hidden");
        compilationResults.classList.add("hidden");
        loader.classList.remove("hidden");
        btnCompile.disabled = true;

        try {
            const response = await fetch("/analyze", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({ source: sourceCode })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || "Ocurrió un error en el servidor.");
            }

            const data = await response.json();
            displayResults(data);
        } catch (error) {
            alert(`Error de compilación: ${error.message}`);
            placeholderResult.classList.remove("hidden");
        } finally {
            loader.classList.add("hidden");
            btnCompile.disabled = false;
        }
    });

    // 4. Display Results in Dashboard
    function displayResults(data) {
        compilationResults.classList.remove("hidden");

        // --- LLM ERROR EXPLANATION ---
        const llmErrorCard = document.getElementById("card-llm-errors");
        const llmErrorExplanation = document.getElementById("llm-error-explanation");
        
        if (data.error_explicacion) {
            llmErrorCard.classList.remove("hidden");
            llmErrorExplanation.innerHTML = parseMarkdown(data.error_explicacion);
        } else {
            llmErrorCard.classList.add("hidden");
        }

        // --- FASE 1: TOKENS ---
        tokenList.innerHTML = "";
        data.tokens.forEach(tok => {
            const pill = document.createElement("div");
            
            // Clean up type names for better representation
            let typeLabel = tok.type;
            let classType = "";
            if (tok.type === "INSTRUCCION_INCORPORAR") {
                typeLabel = "INCORPORAR";
            } else if (tok.type === "INSTRUCCION_MEZCLAR") {
                typeLabel = "MEZCLAR";
            } else if (tok.type === "UNKNOWN") {
                classType = "type-unknown";
            }

            const originClass = tok.origin === "AFD" ? "origin-afd" : "origin-llm";
            pill.className = `token-pill ${originClass} ${classType}`;
            
            pill.innerHTML = `
                <span class="token-type">${typeLabel}</span>
                <span class="token-value">${escapeHtml(tok.value)}</span>
                <span class="token-origin">${tok.origin}</span>
            `;
            tokenList.appendChild(pill);
        });

        // --- FASE 2: SINTAXIS ---
        const syntaxCard = document.getElementById("card-sintaxis");
        if (data.sintaxis.valid) {
            syntaxStatusBadge.textContent = "VÁLIDO";
            syntaxStatusBadge.className = "badge-status valid";
            syntaxDetails.className = "status-msg-box success";
            syntaxDetails.innerHTML = "<strong>Éxito Sintáctico:</strong> La estructura BNF es completamente correcta y se alinea con la gramática formal.";
        } else {
            syntaxStatusBadge.textContent = "ERROR";
            syntaxStatusBadge.className = "badge-status invalid";
            syntaxDetails.className = "status-msg-box danger";
            syntaxDetails.innerHTML = `<strong>Error Sintáctico:</strong> ${escapeHtml(data.sintaxis.error)}`;
        }

        // --- FASE 3: SEMÁNTICA ---
        const semanticCard = document.getElementById("card-semantica");
        ingredientsTags.innerHTML = "";
        detectedIngredientsContainer.classList.add("hidden");

        if (data.semantica.valid) {
            semanticStatusBadge.textContent = "VÁLIDO";
            semanticStatusBadge.className = "badge-status valid";
            
            let htmlContent = "<strong>Éxito Semántico:</strong> El programa pasó la validación del analizador semántico sin errores.";
            
            // Si hay warnings, los mostramos
            if (data.semantica.warnings && data.semantica.warnings.length > 0) {
                htmlContent += `
                    <div class="semantic-warnings">
                        <h4>⚠️ Advertencias:</h4>
                        <ul class="semantic-item-list">
                            ${data.semantica.warnings.map(w => `<li>${escapeHtml(w)}</li>`).join("")}
                        </ul>
                    </div>
                `;
            }
            
            semanticDetails.className = "status-msg-box success";
            semanticDetails.innerHTML = htmlContent;
  
            // Renderizar ingredientes detectados
            if (data.semantica.ingredients && data.semantica.ingredients.length > 0) {
                detectedIngredientsContainer.classList.remove("hidden");
                data.semantica.ingredients.forEach(ing => {
                    const tag = document.createElement("span");
                    tag.className = "tag-ingredient";
                    tag.textContent = ing;
                    ingredientsTags.appendChild(tag);
                });
            }
        } else {
            semanticStatusBadge.textContent = "ERROR";
            semanticStatusBadge.className = "badge-status invalid";
            
            let htmlContent = "<strong>Error Semántico:</strong> Se detectaron problemas en la validación semántica.<br>";
            
            if (data.semantica.errors && data.semantica.errors.length > 0) {
                htmlContent += `
                    <ul class="semantic-item-list" style="margin-top: 0.5rem;">
                        ${data.semantica.errors.map(err => `<li>${escapeHtml(err)}</li>`).join("")}
                    </ul>
                `;
            }
            
            // Mostrar warnings también si existen
            if (data.semantica.warnings && data.semantica.warnings.length > 0) {
                htmlContent += `
                    <div class="semantic-warnings" style="margin-top: 0.75rem;">
                        <h4>⚠️ Advertencias:</h4>
                        <ul class="semantic-item-list">
                            ${data.semantica.warnings.map(w => `<li>${escapeHtml(w)}</li>`).join("")}
                        </ul>
                    </div>
                `;
            }

            semanticDetails.className = "status-msg-box danger";
            semanticDetails.innerHTML = htmlContent;
        }

        // --- FASE 4: AST (ÁRBOL) ---
        renderAST(data.ast, astTree);
    }

    // 5. Render AST to HTML Elements
    function renderAST(ast, container) {
        container.innerHTML = "";
        if (!ast) {
            container.innerHTML = "<p class='section-desc' style='text-align: center;'>No se puede generar el árbol AST (la receta está vacía o es inválida).</p>";
            return;
        }

        const rootUl = document.createElement("ul");
        const rootLi = document.createElement("li");

        // Nodo raíz
        const rootNode = document.createElement("div");
        rootNode.className = "tree-node node-receta";
        rootNode.innerHTML = `
            <span class="tree-node-title">Raíz (Programa)</span>
            <span class="tree-node-value">${escapeHtml(ast.label)}</span>
        `;
        rootLi.appendChild(rootNode);

        if (ast.children && ast.children.length > 0) {
            const childrenUl = document.createElement("ul");
            
            ast.children.forEach(child => {
                const childLi = document.createElement("li");
                
                // Nodo de instrucción
                const childNode = document.createElement("div");
                const nodeClass = child.type === "InstruccionAgregar" ? "node-agregar" : 
                                  child.type === "InstruccionMezclar" ? "node-mezclar" : "node-detail";
                
                childNode.className = `tree-node ${nodeClass}`;
                childNode.innerHTML = `
                    <span class="tree-node-title">${escapeHtml(child.label)}</span>
                    <span class="tree-node-value">${escapeHtml(child.action)}</span>
                `;
                childLi.appendChild(childNode);

                // Sub-árbol para los argumentos de la instrucción
                const leavesUl = document.createElement("ul");
                
                if (child.type === "InstruccionAgregar") {
                    // Argumento 1: Cantidad
                    const qtyLi = document.createElement("li");
                    qtyLi.innerHTML = `
                        <div class="tree-node node-detail">
                            <span class="tree-node-title">Cantidad</span>
                            <span class="tree-node-value">${escapeHtml(child.quantity)}</span>
                        </div>
                    `;
                    leavesUl.appendChild(qtyLi);

                    // Argumento 2: Ingrediente
                    const ingLi = document.createElement("li");
                    ingLi.innerHTML = `
                        <div class="tree-node node-detail">
                            <span class="tree-node-title">Ingrediente</span>
                            <span class="tree-node-value">${escapeHtml(child.ingredient)}</span>
                        </div>
                    `;
                    leavesUl.appendChild(ingLi);
                } else if (child.type === "InstruccionMezclar") {
                    // Argumento 1: Duración
                    const durLi = document.createElement("li");
                    durLi.innerHTML = `
                        <div class="tree-node node-detail">
                            <span class="tree-node-title">Duración</span>
                            <span class="tree-node-value">${escapeHtml(child.duration)} minutos</span>
                        </div>
                    `;
                    leavesUl.appendChild(durLi);

                    // Argumento 2: Detalle (UNKNOWN)
                    const detLi = document.createElement("li");
                    detLi.innerHTML = `
                        <div class="tree-node node-detail">
                            <span class="tree-node-title">Detalle</span>
                            <span class="tree-node-value">${escapeHtml(child.detail)}</span>
                        </div>
                    `;
                    leavesUl.appendChild(detLi);
                } else {
                    const valLi = document.createElement("li");
                    valLi.innerHTML = `
                        <div class="tree-node node-detail">
                            <span class="tree-node-title">Valor</span>
                            <span class="tree-node-value">${escapeHtml(child.value)}</span>
                        </div>
                    `;
                    leavesUl.appendChild(valLi);
                }

                childLi.appendChild(leavesUl);
                childrenUl.appendChild(childLi);
            });
            
            rootLi.appendChild(childrenUl);
        }

        rootUl.appendChild(rootLi);
        container.appendChild(rootUl);
    }

    // Simple Markdown to HTML parser for formatting the LLM response
    function parseMarkdown(md) {
        if (!md) return "";
        let html = md;
        
        // Escape HTML to avoid XSS
        html = html
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;");
            
        // Convert bold **text** or __text__
        html = html.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
        html = html.replace(/__(.*?)__/g, "<strong>$1</strong>");
        
        // Convert inline code `code`
        html = html.replace(/`(.*?)`/g, "<code>$1</code>");
        
        // Convert bullet lists and paragraphs
        const lines = html.split("\n");
        let inList = false;
        let newLines = [];
        
        for (let line of lines) {
            let trimmed = line.trim();
            if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
                if (!inList) {
                    newLines.push("<ul>");
                    inList = true;
                }
                newLines.push(`<li>${trimmed.substring(2)}</li>`);
            } else {
                if (inList) {
                    newLines.push("</ul>");
                    inList = false;
                }
                if (trimmed.length > 0) {
                    if (trimmed.startsWith("### ")) {
                        newLines.push(`<h4>${trimmed.substring(4)}</h4>`);
                    } else if (trimmed.startsWith("## ")) {
                        newLines.push(`<h3>${trimmed.substring(3)}</h3>`);
                    } else if (trimmed.startsWith("# ")) {
                        newLines.push(`<h2>${trimmed.substring(2)}</h2>`);
                    } else {
                        newLines.push(`<p>${trimmed}</p>`);
                    }
                }
            }
        }
        if (inList) {
            newLines.push("</ul>");
        }
        
        return newLines.join("\n");
    }

    // Helper: Escape HTML strings to prevent XSS
    function escapeHtml(str) {
        if (!str) return "";
        return str
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }
});
