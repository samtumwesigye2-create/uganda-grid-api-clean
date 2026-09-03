(() => {
  let lastRecommended='';
  function selectRecommended(dash){
    const next=dash?.next_stop;if(!next?.id)return;
    const current=document.querySelector('.taskRow.selected');
    const currentId=current?.dataset?.id||'';
    const currentText=(current?.textContent||'').toLowerCase();
    const currentBusy=currentText.includes('arrived pickup')||currentText.includes('arrived dropoff')||currentText.includes('en route pickup')||currentText.includes('en route dropoff');
    if(currentBusy)return;
    if(String(currentId)===String(next.id))return;
    const row=document.querySelector(`.taskRow[data-id="${CSS.escape(String(next.id))}"]`);
    if(!row)return;
    row.click();
    if(lastRecommended!==String(next.id)){
      lastRecommended=String(next.id);
      const b=document.getElementById('ugatuMsg');
      if(b){b.className='notice ok';b.textContent=`Next stop ready: ${next.task_number||next.location_text||'assigned stop'} · ${next.priority_reason||'sequenced'}`;b.hidden=false;setTimeout(()=>b.hidden=true,3800)}
    }
  }
  document.addEventListener('ugatu:dashboard-refreshed',e=>selectRecommended(e.detail));
})();
