export interface ToolData {
    tool_name: string;
    description: string;
    inputs: ToolInput[];
    relation?: string;      // kernel relation name — compute runs server-side
    solve_for?: string;     // variable of `relation` to solve for
    output_unit?: string;   // unit to display the result in
    formula_latex?: string;
    outputs?: ToolOutput[];  // Output field definitions
    suggestions?: string[];  // Proactive follow-up suggestions
    workflow_name?: string;  // set for stacked workflows
    steps?: any[];           // workflow steps
    ui_spec?: unknown;       // the validated UISpec (registry renders by type)
}

export interface ToolOutput {
    name: string;
    label: string;
    unit: string;
}

export interface ToolInput {
    name: string;
    label: string;
    type: "text" | "number";
    unit?: string;
    unit_type?: "length" | "force" | "pressure" | "area" | "mass" | "density" | "modulus_of_elasticity";
    default_value?: any;
}

export interface Message {
    role: "user" | "assistant" | "system";
    content: string;
    tool_data?: ToolData;
}

export interface Session {
    id: number;
    title: string;
    context_type: string;
    created_at: string;
}

export interface SessionDetail extends Session {
    messages: Message[];
}
