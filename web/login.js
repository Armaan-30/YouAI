document.getElementById('login-form').onsubmit=async event=>{
  event.preventDefault();
  const error=document.getElementById('login-error');error.textContent='';
  const buttons=[...document.querySelectorAll('button')];buttons.forEach(b=>b.disabled=true);
  try{
    const response=await fetch('/api/auth/'+(event.submitter?.id==='register'?'register':'login'),{
      method:'POST',headers:{'Content-Type':'application/json','X-YouAI':'1'},
      body:JSON.stringify({username:document.getElementById('username').value,password:document.getElementById('password').value,invite:document.getElementById('invite').value})});
    const data=await response.json();if(!response.ok)throw new Error(data.detail||'Sign-in failed.');location.replace('/');
  }catch(e){error.textContent=e.message;}finally{buttons.forEach(b=>b.disabled=false);}
};
