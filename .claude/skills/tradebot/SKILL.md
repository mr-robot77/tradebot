```markdown
# tradebot Development Patterns

> Auto-generated skill from repository analysis

## Overview
This skill teaches you the core development patterns and conventions used in the `tradebot` TypeScript codebase. You'll learn about file naming, import/export styles, commit message patterns, and how to write and run tests. While no specific automation workflows were detected, this guide provides best practices and suggested commands to streamline your development process.

## Coding Conventions

### File Naming
- Use **snake_case** for all file names.
  - Example:  
    ```
    trade_utils.ts
    order_manager.test.ts
    ```

### Import Style
- Use **relative imports** for referencing other modules.
  - Example:
    ```typescript
    import { calculateProfit } from './trade_utils';
    ```

### Export Style
- Use **named exports** for all exported functions, types, or constants.
  - Example:
    ```typescript
    // trade_utils.ts
    export function calculateProfit(...) { ... }
    ```

### Commit Messages
- Mixed commit types, but commonly use the `ci` prefix for continuous integration-related changes.
- Keep commit messages concise (average ~41 characters).
  - Example:
    ```
    ci: add github actions workflow
    ```

## Workflows

### Code Changes and Commits
**Trigger:** When making any code changes  
**Command:** `/commit`

1. Make your code changes following the conventions above.
2. Stage your changes:  
   ```bash
   git add .
   ```
3. Commit with a concise message, using `ci:` prefix for CI-related changes:  
   ```bash
   git commit -m "ci: update build script"
   ```
4. Push your changes:  
   ```bash
   git push
   ```

### Adding a New Module
**Trigger:** When creating a new feature or utility  
**Command:** `/add-module`

1. Create a new file using snake_case, e.g., `order_manager.ts`.
2. Write your functions or classes using named exports.
3. Import your module using a relative path where needed.

   Example:
   ```typescript
   // order_manager.ts
   export function createOrder(...) { ... }

   // elsewhere
   import { createOrder } from './order_manager';
   ```

### Writing and Running Tests
**Trigger:** When adding or updating features  
**Command:** `/test`

1. Create a test file with the pattern `*.test.ts`, e.g., `trade_utils.test.ts`.
2. Write your tests using the project's preferred (but unspecified) testing framework.
3. Run your tests using the appropriate command for your test runner (e.g., `npm test`).

   Example:
   ```typescript
   // trade_utils.test.ts
   import { calculateProfit } from './trade_utils';

   test('calculates profit correctly', () => {
     expect(calculateProfit(...)).toBe(...);
   });
   ```

## Testing Patterns

- Test files follow the `*.test.ts` naming convention.
- The specific testing framework is not specified; use the project's existing setup.
- Place tests alongside or near the modules they test.

## Commands
| Command      | Purpose                                         |
|--------------|-------------------------------------------------|
| /commit      | Commit code changes following conventions        |
| /add-module  | Add a new module with correct naming/exports     |
| /test        | Write and run tests for your code                |
```