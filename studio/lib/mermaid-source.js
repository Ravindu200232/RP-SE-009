// Whether a saved diagram source is Mermaid at all.
const DECLARATION = /^[ \t]*(?:(?:flowchart|graph)(?:[ \t]+(?:TB|TD|BT|RL|LR))?|sequenceDiagram|classDiagram(?:-v2)?|stateDiagram(?:-v2)?|erDiagram)[ \t]*;?[ \t]*\r?$/im

export const isMermaid = (source) => DECLARATION.test(String(source || ''))
