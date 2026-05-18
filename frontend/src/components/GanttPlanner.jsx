import React, { useRef } from 'react'
import axios from 'axios'

function toMinutes(dt){
  return (new Date(dt)).getHours()*60 + (new Date(dt)).getMinutes()
}

export default function GanttPlanner({day, onSelect, onChange}){
  const containerRef = useRef(null)
  const tasks = (day && day.scheduled) || []

  function handleDragEnd(e, task){
    // naive: compute delta in minutes from dataTransfer
    const delta = parseInt(e.dataTransfer.getData('minutes') || '0',10)
    if(!delta) return
    const start = new Date(task.start_time)
    const end = new Date(task.end_time)
    const newStart = new Date(start.getTime() + delta*60000)
    const newEnd = new Date(end.getTime() + delta*60000)

    // send update to backend
    axios.patch(`/api/schedule/task/${task.id}`, { start_time: newStart.toISOString(), end_time: newEnd.toISOString() })
      .then(()=> onChange())
      .catch(err=>{ console.error(err); alert('Update failed') })
  }

  function handleDragStart(e, task){
    // store minutes delta placeholder (UI would compute real delta)
    e.dataTransfer.setData('minutes', '15')
    e.dataTransfer.effectAllowed = 'move'
    e.target.classList.add('dragging')
  }
  function handleDragCancel(e){
    e.target.classList.remove('dragging')
  }

  // Simple timeline: compute left and width based on minutes since DAY_START (08:00)
  const DAY_START_H = 8
  return (
    <div style={{position:'relative',height:'600px',border:'1px solid #eee'}} ref={containerRef}>
      {tasks.map(t=>{
        const s = new Date(t.start_time)
        const e = new Date(t.end_time)
        const left = ((s.getHours()+s.getMinutes()/60) - DAY_START_H) * 100
        const width = ((e - s)/60000)/60 * 100
        return (
          <div
            key={t.job_id + '-' + t.step}
            draggable
            onDragStart={(ev)=>handleDragStart(ev,t)}
            onDragEnd={(ev)=>handleDragEnd(ev,t)}
            onDragCancel={handleDragCancel}
            onClick={()=>onSelect(t)}
            className="task"
            style={{left:left+'px', top:20 + Math.random()*200 + 'px', width: Math.max(60, width+'px')}}
          >
            {t.job_id} ({t.step})
          </div>
        )
      })}
    </div>
  )
}
