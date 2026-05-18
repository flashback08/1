import React from 'react'

export default function ResourceSidebar({day}){
  const analysts = (day && day.analysts) || []
  const instruments = (day && day.instruments) || []
  return (
    <div>
      <h3>Analysts</h3>
      <ul>
        {analysts.map(a=> <li key={a.id}>{a.display_name || a.username}</li>)}
      </ul>
      <h3>Instruments</h3>
      <ul>
        {instruments.map(i=> <li key={i.id}>{i.name} ({i.type})</li>)}
      </ul>
    </div>
  )
}
