# Cursor Rules for Python, Reflex & FastAPI Development

This directory contains specialized Cursor AI rules organized by domain for Python, Reflex full-stack, and FastAPI backend development.

## 📋 Rule Organization

According to [Cursor Rules Documentation](https://cursor.com/docs/context/rules), rule files:
- Must use `.mdc` file extension (Markdown with Context)
- Must include metadata header with `description` and `globs`
- Should be organized in `.cursor/rules/` directory
- Are automatically discovered and applied by Cursor AI

## 📁 File Structure

### Root Coordination
- **index.mdc** - Main index coordinating all domain-specific rules with quick reference

### Core Framework (Reflex)
- **reflex-framework-base.mdc** - Core Reflex patterns, project structure, compile-time vs runtime
- **reflex-state-model.mdc** - State management (`rx.State`), computed vars, `rx.Model` for database
- **reflex-var-system.mdc** - Var system for reactive UI bindings and type safety
- **reflex-events-handlers.mdc** - Event handling, async operations, background tasks

### Components & UI
- **reflex-components-base.mdc** - Core component patterns and built-in components
- **reflex-layout.mdc** - Layout components (vstack, hstack, container, grid, flex)
- **reflex-typography.mdc** - Text, heading, and typography components
- **reflex-forms.mdc** - Form components, input validation, submission patterns
- **reflex-data-display.mdc** - Tables, cards, lists, data presentation
- **reflex-overlay.mdc** - Modal, dialog, popover, drawer, tooltip components
- **reflex-disclosure-media-utils.mdc** - Accordion, tabs, collapsible, media components

### Advanced Component Libraries
- **reflex-charts.mdc** - Chart components (recharts integration)
- **reflex-agchart.mdc** - AG Charts for advanced data visualization
- **reflex-aggrid.mdc** - AG Grid for powerful data tables
- **reflex-tables.mdc** - Advanced table patterns and configurations
- **reflex-dashboard.mdc** - Dashboard layouts and admin interfaces

### Application Features
- **reflex-app-config.mdc** - App configuration, rxconfig.py, project settings
- **reflex-cli-env-utils.mdc** - CLI commands, environment setup, deployment
- **reflex-browser-apis.mdc** - Browser APIs (localStorage, cookies, navigation)
- **reflex-dynamic-rendering.mdc** - Dynamic routing, conditional rendering
- **reflex-azure-auth.mdc** - Authentication with Azure AD and reflex-local-auth
- **reflex-enterprise.mdc** - Enterprise patterns, scalability, production

### Testing
- **reflex-tests.mdc** - Comprehensive testing with Playwright and pytest

### Backend Development
- **fastapi.mdc** - FastAPI patterns for backend APIs, webhooks, integrations
- **sqlalchemy.mdc** - Database patterns with SQLAlchemy/SQLModel

## 🎯 Usage

### In Cursor AI
Rules are automatically applied based on file patterns (globs) when:
- Creating new files
- Editing existing files
- Asking questions about code

### Manual Reference
To explicitly reference a rule:
1. Use `@Rules` in Cursor chat
2. Select specific rule file from `.cursor/rules/`
3. Rules apply automatically based on file context

### Glob Patterns
Each rule file specifies which files it applies to:

```yaml
---
description: Rule description
globs: 
  - "**/*.py"           # All Python files
  - "**/rxconfig.py"    # Config files
  - "tests/**/*.py"     # Test files
---
```

## 🚀 Quick Start

### For Reflex Development
1. Start with **index.mdc** for overview
2. Reference **reflex-framework-base.mdc** for core concepts
3. Use **reflex-state-model.mdc** for state management
4. Consult component-specific rules as needed

### For FastAPI Backend
1. Check **fastapi.mdc** for API patterns
2. Use **sqlalchemy.mdc** for database operations
3. Reference **reflex-azure-auth.mdc** for authentication

### For Testing
1. Follow **reflex-tests.mdc** for Playwright/pytest patterns
2. Use fixtures and test patterns from examples

## 📝 Rule File Format

Each `.mdc` file follows this structure:

```markdown
---
description: Brief description of what this rule covers
globs: 
  - "**/*.py"
  - "path/pattern/*.py"
---

# Rule Title

You are an expert in [domain].

## Section 1
Content with examples...

## Section 2
More guidance...
```

### Metadata Requirements
- `description`: Clear, concise description (used by Cursor AI for context)
- `globs`: Array of glob patterns for file matching

### Content Structure
- Start with "You are an expert in..." framing
- Organize into logical sections
- Include code examples
- Highlight best practices and common pitfalls

## 🔧 Customization

### Adding New Rules
1. Create new `.mdc` file in `.cursor/rules/`
2. Add metadata header with description and globs
3. Update **index.mdc** to reference new rule
4. Follow existing rule structure for consistency

### Modifying Rules
1. Edit the specific `.mdc` file
2. Maintain metadata header format
3. Keep examples up-to-date
4. Test changes with relevant code files

## 📚 Best Practices

### When Writing Rules
✅ **DO:**
- Use specific, actionable guidance
- Include code examples
- Highlight common mistakes
- Reference related rules
- Keep sections focused

❌ **DON'T:**
- Write vague or generic advice
- Duplicate content across files
- Include outdated examples
- Forget to update globs
- Create overly long files

### Rule Organization
- **One domain per file**: Each rule file focuses on one functional area
- **Clear naming**: Use descriptive, hyphenated names
- **Logical grouping**: Related rules should cross-reference each other
- **Index coordination**: Main index ties everything together

## 🔗 Related Files

- **AGENTS.md** - Agent instructions file (replaces .cursorrules)
- **rxconfig.py** - Reflex app configuration
- **requirements.txt** - Python dependencies

## 📖 References

- [Cursor Rules Documentation](https://cursor.com/docs/context/rules)
- [Reflex Documentation](https://reflex.dev/docs)
- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org)

## 🤝 Contributing

When adding or modifying rules:
1. Ensure `.mdc` format with proper metadata
2. Add to appropriate domain category
3. Update index.mdc with references
4. Include practical examples
5. Test with actual code files

---

**Last Updated**: 2025-10-13
**Cursor Version**: Compatible with Cursor 0.2.5+
