import React, { useState } from 'react'
import ResourceSidebar from './ResourceSidebar'
import JobsPanel from './JobsPanel'
import GanttPlanner from './GanttPlanner'
import InspectorPane from './InspectorPane'

export default function PlannerDashboard({day, refreshDay}){
  const [selected, setSelected] = useState(null)

  return (
    <div className="app-main">
      <aside className="sidebar"><ResourceSidebar day={day} /></aside>
      <section className="jobs"><JobsPanel day={day} onAutoPlan={refreshDay} /></section>
      <main className="gantt"><GanttPlanner day={day} onSelect={setSelected} onChange={refreshDay} /></main>
      <aside className="inspect"><InspectorPane task={selected} /></aside>
    </div>
  )
}
