import React, { useState, useEffect } from 'react'
import axios from 'axios'
import PlannerDashboard from './components/PlannerDashboard'
import DataUploadPanel from './components/DataUploadPanel'

export default function App(){
  const [date, setDate] = useState(new Date().toISOString().slice(0,10))
  const [payload, setPayload] = useState(null)

  useEffect(()=>{
    fetchDay(date)
  },[date])

  async function fetchDay(d){
    try{
      const res = await axios.get(`/api/planner/day?date=${d}`)
      setPayload(res.data)
    }catch(e){
      console.error(e)
      setPayload({date:d, scheduled:[], unassigned:[]})
    }
  }

  return (
    <div className="app-root">
      <header className="app-header">
        <h1>QC Allocation Planner</h1>
        <input type="date" value={date} onChange={e=>setDate(e.target.value)} />
      </header>
      <DataUploadPanel />
      <PlannerDashboard day={payload} refreshDay={()=>fetchDay(date)} />
    </div>
  )
}
