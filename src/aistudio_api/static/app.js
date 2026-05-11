
function app(){return{
  view:'chat',sidebarOpen:false,configOpen:false,openSelect:null,
  stats:{},rotationMode:'round_robin',rotCfg:{mode:'round_robin',cooldown:60},
  accounts:[],rotationAccounts:{},activeId:'',activeAccount:{},accountsLoading:false,accountsError:'',activeAccountNote:'',rotationError:'',savingRotation:false,forcingNext:false,
  accountBusy:{},renameId:'',renameDraft:'',deleteConfirmId:'',
  loginStarting:false,loginPollTimer:null,loginSession:{id:'',status:'',email:'',error:''},
  models:[],model:'',
  msgs:[],draft:'',busy:false,
  cfg:{thinking:'off',search:'off',stream:'on',temperature:1.0,topP:1.0,maxTokens:8192,safety:'on'},
  toast:{show:false,msg:'',t:null},

  init(){this.loadModels();this.loadStats();this.loadAccounts();this.loadRotation();document.addEventListener('click',()=>this.openSelect=null)},
  go(v){this.view=v;this.sidebarOpen=false;if(v==='dashboard')this.loadStats();if(v==='accounts'){this.loadAccounts();this.loadRotation()}},
  showToast(m){this.toast.msg=m;this.toast.show=true;if(this.toast.t)clearTimeout(this.toast.t);this.toast.t=setTimeout(()=>this.toast.show=false,3000)},
  toggleSelect(k,e){e.stopPropagation();this.openSelect=this.openSelect===k?null:k},
  selectOpt(k,model,val){this[model]=val;this.openSelect=null},

  async loadModels(){try{const r=await fetch('/v1/models');const d=await r.json();this.models=d.data||[];if(!this.model&&this.models.length)this.model=this.models[0].id}catch(e){}},
  async loadStats(){try{const r=await fetch('/stats');const d=await r.json();this.stats=d.models||{}}catch(e){}},
  async fetchJson(url,opts){const r=await fetch(url,opts);let d=null;try{d=await r.json()}catch(e){}if(!r.ok){const detail=d?.detail;const msg=typeof detail==='string'?detail:(detail?JSON.stringify(detail):r.statusText||`HTTP ${r.status}`);const err=new Error(msg);err.status=r.status;throw err}return d},
  errMsg(e,fallback){return e?.message||fallback},
  async refreshAccountData(){await Promise.all([this.loadAccounts(),this.loadRotation()])},
  async loadAccounts(){this.accountsLoading=true;this.accountsError='';this.activeAccountNote='';try{this.accounts=await this.fetchJson('/accounts')||[]}catch(e){this.accounts=[];this.accountsError='账号列表加载失败：'+this.errMsg(e,'请求失败')}try{const a=await this.fetchJson('/accounts/active');this.activeId=a?.id||'';this.activeAccount=a||{}}catch(e){this.activeId='';this.activeAccount={};this.activeAccountNote=e.status===404?'当前没有激活账号':'活跃账号加载失败：'+this.errMsg(e,'请求失败')}finally{this.accountsLoading=false}},
  async loadRotation(){this.rotationError='';try{const d=await this.fetchJson('/rotation');this.rotationMode=d?.mode||'round_robin';this.rotCfg.mode=d?.mode||'round_robin';this.rotCfg.cooldown=d?.cooldown_seconds||60;this.rotationAccounts=d?.accounts||{}}catch(e){this.rotationError='轮询信息加载失败：'+this.errMsg(e,'请求失败')}},

  get accountRows(){return this.accounts.map(a=>({...(this.rotationAccounts[a.id]||{}),...a}))},
  get accountCount(){return this.accounts.length},
  get activeLabel(){return this.activeAccount.email||this.activeAccount.name||this.activeId||'暂无'},
  get loginBusy(){return this.loginStarting||this.loginSession.status==='pending'},
  get totalReqs(){return Object.values(this.stats).reduce((s,v)=>s+(v.requests||0),0)},
  get totalRL(){return Object.values(this.stats).reduce((s,v)=>s+(v.rate_limited||0),0)},

  accountLabel(a){return a?.email||a?.name||a?.id||'未知账号'},
  setAccountBusy(action,id,busy){const key=`${action}:${id}`;const next={...this.accountBusy};if(busy)next[key]=true;else delete next[key];this.accountBusy=next},
  isAccountBusy(action,id){return !!this.accountBusy[`${action}:${id}`]},
  isRowBusy(id){return this.isAccountBusy('activate',id)||this.isAccountBusy('rename',id)||this.isAccountBusy('delete',id)},
  loginStatusText(){const s=this.loginSession.status;if(s==='pending')return'等待浏览器登录';if(s==='completed')return'登录完成';if(s==='failed')return'登录失败';return'未开始'},
  loginStatusClass(){const s=this.loginSession.status;if(s==='completed')return'notice-success';if(s==='failed')return'notice-error';return'notice-info'},
  async saveRotation(){if(this.savingRotation)return;this.savingRotation=true;try{await this.fetchJson('/rotation/mode',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mode:this.rotCfg.mode,cooldown_seconds:this.rotCfg.cooldown})});this.showToast('已保存');await this.loadRotation()}catch(e){this.showToast('保存失败：'+this.errMsg(e,'请求失败'))}finally{this.savingRotation=false}},
  async forceNext(){if(this.forcingNext)return;this.forcingNext=true;try{await this.fetchJson('/rotation/next',{method:'POST'});this.showToast('已切换账号');await this.refreshAccountData()}catch(e){this.showToast('切换失败：'+this.errMsg(e,'请求失败'))}finally{this.forcingNext=false}},
  async activateAccount(id){if(this.isAccountBusy('activate',id))return;this.setAccountBusy('activate',id,true);try{await this.fetchJson(`/accounts/${encodeURIComponent(id)}/activate`,{method:'POST'});this.showToast('已激活');await this.refreshAccountData()}catch(e){this.showToast('激活失败：'+this.errMsg(e,'请求失败'))}finally{this.setAccountBusy('activate',id,false)}},
  beginRename(a){this.renameId=a.id;this.renameDraft=a.name||a.email||'';this.deleteConfirmId=''},
  cancelRename(){this.renameId='';this.renameDraft=''},
  async renameAccount(a){const id=a.id;const name=this.renameDraft.trim();if(!name){this.showToast('名称不能为空');return}if(name===a.name){this.cancelRename();return}if(this.isAccountBusy('rename',id))return;this.setAccountBusy('rename',id,true);try{await this.fetchJson(`/accounts/${encodeURIComponent(id)}`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({name})});this.showToast('已重命名');this.cancelRename();await this.refreshAccountData()}catch(e){this.showToast('重命名失败：'+this.errMsg(e,'请求失败'))}finally{this.setAccountBusy('rename',id,false)}},
  requestDeleteAccount(a){this.deleteConfirmId=a.id;this.renameId='';this.renameDraft=''},
  cancelDelete(){this.deleteConfirmId=''},
  async deleteAccount(a){const id=a.id;if(this.isAccountBusy('delete',id))return;this.setAccountBusy('delete',id,true);try{await this.fetchJson(`/accounts/${encodeURIComponent(id)}`,{method:'DELETE'});this.showToast('已删除 '+this.accountLabel(a));this.deleteConfirmId='';await this.refreshAccountData()}catch(e){this.showToast('删除失败：'+this.errMsg(e,'请求失败'))}finally{this.setAccountBusy('delete',id,false)}},
  clearLoginPoll(){if(this.loginPollTimer){clearTimeout(this.loginPollTimer);this.loginPollTimer=null}},
  async addAccount(){if(this.loginBusy)return;this.loginStarting=true;this.clearLoginPoll();try{const d=await this.fetchJson('/accounts/login/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({})});if(!d?.session_id)throw new Error('登录会话缺少 session_id');this.loginSession={id:d.session_id,status:'pending',email:'',error:''};this.showToast('登录已开始');this.pollLoginStatus()}catch(e){this.loginSession={id:'',status:'failed',email:'',error:this.errMsg(e,'启动登录失败')};this.showToast('启动登录失败：'+this.loginSession.error)}finally{this.loginStarting=false}},
  async pollLoginStatus(){const id=this.loginSession.id;if(!id)return;try{const d=await this.fetchJson(`/accounts/login/status/${encodeURIComponent(id)}`);const status=d?.status||'pending';this.loginSession={id:d?.session_id||id,status,email:d?.email||'',error:d?.error||''};if(status==='completed'){this.clearLoginPoll();this.showToast('登录完成');await this.refreshAccountData();return}if(status==='failed'){this.clearLoginPoll();this.showToast('登录失败：'+(d?.error||'请重试'));return}this.clearLoginPoll();this.loginPollTimer=setTimeout(()=>this.pollLoginStatus(),2000)}catch(e){this.clearLoginPoll();this.loginSession={...this.loginSession,status:'failed',error:this.errMsg(e,'状态查询失败')};this.showToast('登录状态查询失败：'+this.loginSession.error)}},

  resizeTa(){const el=this.$refs.ta;el.style.height='auto';el.style.height=Math.min(el.scrollHeight,200)+'px'},
  scrollDown(){setTimeout(()=>{const el=document.getElementById('chat-scroll');if(el)el.scrollTop=el.scrollHeight},50)},

  async send(){const t=this.draft.trim();if(!t||this.busy||!this.model)return;
    this.msgs.push({role:'user',content:t});this.draft='';this.busy=true;this.resizeTa();this.scrollDown();
    const body={model:this.model,messages:this.msgs.map(m=>({role:m.role,content:m.content}))};
    if(this.cfg.temperature!==1) body.temperature=this.cfg.temperature;
    if(this.cfg.topP!==1) body.top_p=this.cfg.topP;
    if(this.cfg.maxTokens!==8192) body.max_tokens=this.cfg.maxTokens;
    if(this.cfg.stream==='on') body.stream=true;
    if(this.cfg.thinking!=='off') body.thinking=this.cfg.thinking;
    if(this.cfg.search==='on') body.grounding=true;
    if(this.cfg.safety==='off') body.safety_off=true;

    try{const r=await fetch('/v1/chat/completions',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
      if(!r.ok){let e=r.statusText;try{const d=await r.json();if(d.detail)e=JSON.stringify(d.detail)}catch(x){};this.msgs.push({role:'assistant',content:'',error:`Error ${r.status}: ${e}`})}
      else if(this.cfg.stream==='on'){
        const reader=r.body.getReader();const dec=new TextDecoder();this.msgs.push({role:'assistant',content:'',thinking:'',showThinking:false});const idx=this.msgs.length-1;let buf='';
        while(true){const{done,value}=await reader.read();if(done)break;buf+=dec.decode(value,{stream:true});const lines=buf.split('\n');buf=lines.pop();
          for(const ln of lines){if(ln.startsWith('data: ')&&ln!=='data: [DONE]'){try{const d=JSON.parse(ln.slice(6));const delta=d.choices?.[0]?.delta||{};
            const c=delta.content;if(c)this.msgs[idx].content+=c;
            const th=delta.reasoning_content||delta.thinking||delta.reasoning;if(th)this.msgs[idx].thinking+=th;
          }catch(e){}}}
          this.scrollDown()}
      }else{const d=await r.json();const msg=d.choices?.[0]?.message||{};
        this.msgs.push({role:'assistant',content:msg.content||'(无响应内容)',thinking:msg.reasoning_content||msg.thinking||msg.reasoning||'',showThinking:false})}}
    catch(e){this.msgs.push({role:'assistant',content:'',error:e.message})}
    finally{this.busy=false;this.scrollDown()}},

  fmtDate(s){if(!s)return'-';try{return new Date(s).toLocaleString()}catch(e){return s}}
}}
