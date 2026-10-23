"use client";

import type { DiagramComponent } from "./primitives";
import { DIAGRAMS as general } from "./general";
import { DIAGRAMS as fasteners } from "./fasteners";
import { DIAGRAMS as bearings } from "./bearings";
import { DIAGRAMS as beams } from "./beams";
import { DIAGRAMS as transmission } from "./transmission";
import { DIAGRAMS as structural } from "./structural";

export const DIAGRAMS: Record<string, DiagramComponent> = {
    ...general,
    ...fasteners,
    ...bearings,
    ...beams,
    ...transmission,
    ...structural,
};

export function Diagram({ id, params, inputs }: { id: string; params: Record<string, any>; inputs: Record<string, any> }) {
    const C = DIAGRAMS[id];
    if (!C) return null;
    return <C params={params} inputs={inputs} />;
}
