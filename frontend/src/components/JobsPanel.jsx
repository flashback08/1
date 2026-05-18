import React from 'react'
import axios from 'axios'

export default function JobsPanel({day, onAutoPlan}){
  const jobs = (day && day.unassigned) || []

  async function autoPlan(){
    try{
      await axios.post('/api/schedule/plan', { date: day?.date })
      onAutoPlan()
    }catch(e){
      console.error(e)
      alert('Auto-plan failed')
    }
  }

  return (
    <div>
      <h3>Jobs / Backlog</h3>
      <button onClick={autoPlan}>Auto-Plan Day</button>
      <ul>
        {jobs.map(j=> <li key={j.job_id}>{j.job_id} — {j.reason || ''}</li>)}
      </ul>
    </div>
  )
}
