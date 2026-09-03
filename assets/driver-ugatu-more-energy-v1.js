(() => {
  const $=id=>document.getElementById(id);
  function install(){
    const energy=$('vehicleEnergy');
    if(!energy||$('vehicleEnergyMode'))return;
    const label=document.createElement('label');label.id='vehicleEnergyModeLabel';label.textContent='Fuel / Energy Type';label.hidden=true;
    const select=document.createElement('select');select.id='vehicleEnergyMode';select.hidden=true;select.innerHTML='<option value="FUEL">FUEL</option><option value="CHARGE">EV CHARGE</option><option value="ODOMETER">ODOMETER ONLY</option>';
    energy.parentNode.insertBefore(label,energy);energy.parentNode.insertBefore(select,energy);
    document.querySelector('[data-more="fuel"]')?.addEventListener('click',()=>{label.hidden=false;select.hidden=false;select.value='FUEL';setTimeout(()=>select.focus(),30)});
    document.querySelectorAll('[data-more]:not([data-more="fuel"])').forEach(b=>b.addEventListener('click',()=>{label.hidden=true;select.hidden=true}));
    select.addEventListener('change',()=>{
      const mode=select.value;$('vehicleEventType').value=mode;
      $('fuelLabel').textContent=mode==='CHARGE'?'Charge energy (kWh)':mode==='FUEL'?'Fuel amount':'Odometer is recorded above';
      energy.disabled=mode==='ODOMETER';if(mode==='ODOMETER')energy.value='';
    });
    $('vehicleEventSubmit')?.addEventListener('click',()=>{if(!select.hidden)$('vehicleEventType').value=select.value},true);
  }
  install();
})();