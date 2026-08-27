// Reader guidance for saved revisions created before diagram metadata became
// part of the SRS artifact. New revisions receive the same fields from the SRS
// service; these fallbacks keep the current and historical UI equally useful.
export const DIAGRAM_GUIDE = {
  use_case: {
    question: 'What is a Use Case Diagram?',
    definition: 'A UML use case diagram shows the system boundary, the external actors that use it, and the observable goals they expect it to fulfil.',
    drawingRules: [
      'Start with actors outside one named system boundary and actor goals inside it.',
      'Connect actors only to goals supported by approved roles and capabilities.',
      'Use include, extend, or generalization only when it is explicit in the SRS.',
    ],
  },
  sequence: {
    question: 'What is a Sequence Diagram?',
    definition: 'A UML sequence diagram shows how an actor and system participants exchange messages for one scenario, with time progressing from top to bottom.',
    drawingRules: [
      'Start with the initiating actor, application participants, and lifelines.',
      'Draw requests in execution order and show their return messages.',
      'Use conditional, optional, loop, or parallel fragments only when specified.',
    ],
  },
  erd: {
    question: 'What is an Entity-Relationship Diagram?',
    definition: 'An ER diagram is a database blueprint showing persistent entities, attributes, keys, relationships, and supported cardinalities.',
    drawingRules: [
      'Start from approved entities and list typed primary- and foreign-key attributes.',
      'Connect only explicit relationships or resolvable foreign-key references.',
      'Show cardinality and optionality only when the schema supports them.',
    ],
  },
  activity: {
    question: 'What is an Activity Diagram?',
    definition: 'A UML activity diagram models a workflow as actions connected by control flow, including supported choices, loops, and concurrent work.',
    drawingRules: [
      'Start at one initial node, follow the ordered workflow, and finish at a final node.',
      'Use decision and merge nodes only for explicit guarded alternatives.',
      'Use fork and join bars only for explicitly parallel activities.',
    ],
  },
  class_object: {
    question: 'What is a Class & Object Diagram?',
    definition: 'A UML class diagram describes static types, attributes, operations, and relationships; an object view shows an illustrative runtime instance.',
    drawingRules: [
      'Start with one compartmented class box per supported domain type.',
      'List typed attributes and operations only when present in the SRS model.',
      'Add multiplicity, aggregation, composition, or inheritance only with evidence.',
    ],
  },
  state_machine: {
    question: 'What is a State Machine Diagram?',
    definition: "A UML state machine shows the legal states in one object's lifecycle and the events or conditions that permit each transition.",
    drawingRules: [
      'Start from an initial pseudo-state and one explicitly modelled lifecycle field.',
      'Draw only legal from-state to to-state transitions stated by requirements.',
      'If transitions are absent, explain the evidence gap instead of inventing them.',
    ],
  },
  dfd: {
    question: 'What is a Data Flow Diagram?',
    definition: 'A data flow diagram shows how named information enters the system, is transformed by processes, is stored, and leaves for external entities.',
    drawingRules: [
      'Start with external entities, numbered verb–noun processes, and data stores.',
      'Label every arrow with the actual data being moved.',
      'Avoid direct entity-to-store flow and black-hole or miracle processes.',
    ],
  },
  bpmn: {
    question: 'What is a BPMN Process Diagram?',
    definition: 'A BPMN process diagram models a business process with events, tasks, gateways, and participant lanes that make responsibility and hand-offs explicit.',
    drawingRules: [
      'Start with a named pool, horizontal responsibility lanes, and a start event.',
      'Place each task in the responsible participant lane and follow sequence flow.',
      'Use gateways only for explicit branches and finish with an end event.',
    ],
  },
  system_context: {
    question: 'What is a System Context Diagram?',
    definition: 'A system context diagram defines the software boundary and its externally visible relationships with people, external systems, and persistent data.',
    drawingRules: [
      'Start with one central system boundary and keep internal detail minimal.',
      'Place people and external systems outside the boundary.',
      'Label supported interactions and omit unsupported integrations.',
    ],
  },
  component: {
    question: 'What is a Component Diagram?',
    definition: 'A UML component diagram shows modular software parts, the interfaces or ports through which they collaborate, and their required dependencies.',
    drawingRules: [
      'Start with presentation, application/domain, and data/external groups.',
      'Give each component one responsibility and connect dependencies through ports.',
      'Show provided or required interfaces only for supported service boundaries.',
    ],
  },
  deployment: {
    question: 'What is a Deployment Diagram?',
    definition: 'A UML deployment diagram shows runtime nodes, hosted software artifacts, and communication paths in the physical execution topology.',
    drawingRules: [
      'Start with client, application host, and data host nodes required by the stack.',
      'Nest software artifacts inside the nodes on which they execute.',
      'Label protocols and add external nodes only when required by the SRS.',
    ],
  },
}

export const DIAGRAM_NOTATION = {
  use_case: ['Stick figure — actor', 'Oval — actor goal / use case', 'Rectangle — system boundary', 'Solid line — association'],
  sequence: ['Box and dashed line — participant lifeline', 'Solid arrow — request/call', 'Dashed arrow — return', 'Time runs top to bottom'],
  erd: ['Entity box — table and attributes', 'PK / FK — primary and foreign key', "Bar / crow's foot — one / many"],
  activity: ['Filled circle — initial node', 'Rounded rectangle — action', 'Diamond — decision or merge', 'Bullseye — final node'],
  class_object: ['Three-part box — class, attributes, operations', '+ / − — public / private', 'Association labels — multiplicity', 'Underlined name — object instance'],
  state_machine: ['Filled circle — initial pseudo-state', 'Rounded rectangle — state', 'Labeled arrow — legal transition', 'Bullseye — final pseudo-state'],
  dfd: ['Rectangle — external entity', 'Rounded process — data transformation', 'Open-ended box — data store', 'Labeled arrow — data flow'],
  bpmn: ['Thin / thick circle — start / end event', 'Rounded rectangle — task', 'Diamond — gateway', 'Pool and lanes — participant responsibility'],
  system_context: ['Central boundary — system in scope', 'Outside box — actor or external system', 'Cylinder — persistent data', 'Labeled arrow — external relationship'],
  component: ['Component glyph box — modular component', 'Square — port', 'Arrow — supported dependency', 'Bands — architectural layers'],
  deployment: ['3-D box — runtime node', 'Nested label — hosted artifact', 'Labeled line — communication path', 'Outside box — external service'],
}

export function guideForDiagram(kind) {
  const guide = DIAGRAM_GUIDE[kind] || {
    question: `What is this ${String(kind || 'diagram').replaceAll('_', ' ')}?`,
    definition: 'This view is derived from the approved software requirements.',
    drawingRules: ['Start with only the elements and relationships supported by the SRS.'],
  }
  return { ...guide, notation: DIAGRAM_NOTATION[kind] || [] }
}
