import React from 'react'

export default function InspectorPane({task}){
  if(!task) return <div><em>No selection</em></div>
  return (
    <div>
      <h3>Task</h3>
      <p><strong>Job:</strong> {task.job_id}</p>
      <p><strong>Step:</strong> {task.step}</p>
      <p><strong>Analyst:</strong> {task.analyst_id}</p>
      <p><strong>Instrument:</strong> {task.instrument_id}</p>
      <p><strong>Start:</strong> {task.start_time}</p>
      <p><strong>End:</strong> {task.end_time}</p>
    </div>
  )
}
