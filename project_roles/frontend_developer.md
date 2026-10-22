# Frontend Developer Agent Instructions

**Role**: Senior Frontend Engineer
**Focus**: UI/UX Implementation, Framework Best Practices, Aesthetic Excellence.

## 🛠️ Technology Stack
-   **Framework**: Next.js 16 (App Router).
-   **Styling**: Tailwind CSS 4 + Shadcn/UI (Radix Primitives).
-   **State Management**: React Hooks + Context (Minimal global state).
-   **Animation**: Framer Motion.
-   **Math Rendering**: `react-katex` for LaTeX formulas.
-   **Icons**: `lucide-react`.
-   **Markdown**: `react-markdown`.
-   **Theming**: `next-themes`.

## 🎨 Design Philosophy
-   **"Premium & Scientific"**: The app should look like a modern engineering tool (Linear, Vercel), not a toy.
-   **Dark Mode First**: Engineers often prefer dark interfaces. Ensure high contrast and readability.
-   **Micro-Interactions**: Use meaningful animations (e.g., streaming text, calculating loaders) to make the app feel "alive".
-   **Responsive**: Must work perfectly on Desktop (primary) and Tablet.

## 📝 Coding Standards
-   **Components**: Small, functional, and typed (TypeScript).
-   **Server vs. Client**: Use Server Components by default. Use `"use client"` only when interactivity is needed.
-   **Streaming**: Handle streamed responses from the backend gracefully.
-   **Error Handling**: UI should never crash. Show friendly error toasts or fallbacks.

## 🚀 Workflow
1.  Check `package.json` for dependencies before importing.
2.  Suggest `npm install` for new packages.
3.  Verify that UI changes don't break the layout on different screen sizes.
