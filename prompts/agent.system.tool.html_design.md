# Tool: html_design

Description (FR): Génère du HTML/CSS professionnel avec design, charts et colorimétrie pour créer des présentations visuelles. L'IA peut spécifier le thème, les couleurs, et les types de graphiques. Le HTML généré peut être prévisualisé ou converti en PowerPoint/PDF via `html_to_presentation`.

Description (EN): Generates professional HTML/CSS with design, charts, and color schemes for visual presentations. The AI can specify theme, colors, and chart types. Generated HTML can be previewed or converted to PowerPoint/PDF via `html_to_presentation`.

Arguments:
- content (string, required): Detailed description of presentation content (e.g., "3-slide sales presentation: title, bar chart, conclusion").
- theme (string, optional): Visual theme ("modern", "corporate", "creative", "minimal"). Default from settings.
- colors (array of strings, optional): Hex color palette (e.g., ["#3498db", "#e74c3c", "#2ecc71"]).
- chart_type (string, optional): Chart type if applicable ("bar", "line", "pie", "doughnut", "radar").
- chart_data (object, optional): Chart data with labels and datasets (e.g., {"labels": ["Q1", "Q2"], "datasets": [{"data": [10, 20]}]}).

Behavior:
- Uses utility LLM to generate complete HTML/CSS based on content and theme.
- Injects charts using configured library (Chart.js, Plotly, or Matplotlib).
- Saves HTML to `outputs/presentations/design_{timestamp}.html`.
- Returns path for preview or conversion.

Examples:

```json
{
  "thoughts": ["User wants a modern sales presentation with bar chart"],
  "headline": "Designing HTML presentation",
  "tool_name": "html_design",
  "tool_args": {
    "content": "Sales presentation with 3 slides: 1) Title 'Q4 Results', 2) Bar chart showing revenue by region, 3) Conclusion with key takeaways",
    "theme": "modern",
    "colors": ["#3498db", "#e74c3c", "#2ecc71"],
    "chart_type": "bar",
    "chart_data": {
      "labels": ["North", "South", "East", "West"],
      "datasets": [{"label": "Revenue", "data": [120, 90, 150, 80]}]
    }
  }
}
```

```json
{
  "thoughts": ["Create a corporate-themed business plan presentation"],
  "headline": "Business plan HTML design",
  "tool_name": "html_design",
  "tool_args": {
    "content": "Business plan with 5 slides: executive summary, market analysis with pie chart, financial projections with line chart, team, and call to action",
    "theme": "corporate",
    "colors": ["#2c3e50", "#34495e", "#7f8c8d"]
  }
}
```

Bonnes pratiques / Best practices:
- Décrire le contenu en détail (nombre de slides, titres, éléments visuels).
- Spécifier les couleurs pour cohérence avec la marque.
- Utiliser `chart_data` pour des graphiques précis.
- Prévisualiser le HTML avant conversion (si `ppt_enable_preview` activé).
- Combiner avec `html_to_presentation` pour générer PPTX/PDF.

Erreurs courantes / Common errors:
- "PowerPoint generation is disabled" → Activer dans Settings > PowerPoint & PDF Generation.
- "Missing required argument: content" → Fournir une description du contenu.
- Chart library errors → Vérifier que la bibliothèque configurée est disponible.
