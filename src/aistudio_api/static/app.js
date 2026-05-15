
function app(){return{
  view:'chat',sidebarOpen:false,configOpen:false,openSelect:null,
  stats:{},statsTotals:{},rotationMode:'round_robin',rotCfg:{mode:'round_robin',cooldown:60},
  accounts:[],rotationAccounts:{},activeId:'',activeAccount:{},accountsLoading:false,accountsError:'',activeAccountNote:'',rotationError:'',savingRotation:false,forcingNext:false,
  accountBusy:{},renameId:'',renameDraft:'',deleteConfirmId:'',
  credentialImportText:'',credentialImportName:'',credentialImporting:false,credentialExporting:false,credentialExportText:'',credentialError:'',
  loginStarting:false,loginPollTimer:null,loginSession:{id:'',status:'',email:'',error:''},
  models:[],model:'',modelError:'',
  msgs:[],draft:'',busy:false,chatFiles:[],chatFileError:'',
  cfg:{thinking:'off',search:'off',stream:'on',temperature:1.0,topP:1.0,maxTokens:8192,safety:'on'},
  imageModel:'',imagePrompt:'',imageSize:'1024x1024',imageCount:1,imageBusy:false,imageError:'',imageResults:[],imageHistory:[],imageHistorySelection:{},imageHistoryDeleting:false,imageHistoryError:'',imageSessions:[],activeImageSessionId:'',imageSessionLoading:false,imageSessionSaving:false,imageSessionDeletingId:'',imageSessionError:'',imageLastRequest:null,imageReferences:[],imageBaseImage:null,imageConversation:[],imageReferenceError:'',imagePreview:null,
  toast:{show:false,msg:'',t:null},

  init(){this.loadImageHistory();this.loadImageSessions();this.applyRouteHash();this.loadModels();this.loadStats();this.loadAccounts();this.loadRotation();window.addEventListener('hashchange',()=>this.applyRouteHash());document.addEventListener('click',()=>this.closeSelect());document.addEventListener('keydown',(event)=>this.handleSelectKeydown(event))},
  applyRouteHash(){const route=(window.location.hash||'').replace('#','');if(['chat','images','dashboard','accounts'].includes(route))this.go(route,{syncHash:false})},
  go(v,opts={}){this.view=v;this.sidebarOpen=false;if(opts.syncHash!==false&&window.location.hash!==`#${v}`)window.location.hash=v;if(v==='dashboard')this.loadStats();if(v==='accounts'){this.loadAccounts();this.loadRotation()}if(v==='images'){this.ensureImageDefaults();this.loadImageSessions(false)}},
  showToast(m){this.toast.msg=m;this.toast.show=true;if(this.toast.t)clearTimeout(this.toast.t);this.toast.t=setTimeout(()=>this.toast.show=false,3000)},
  closeSelect(root=null){this.openSelect=null;this.clearSelectHighlights(root)},
  toggleSelect(k,e){e.stopPropagation();const root=e.currentTarget?.closest('.cselect');const opening=this.openSelect!==k;this.openSelect=opening?k:null;if(opening)this.queueSelectHighlight(root);else this.clearSelectHighlights(root)},
  selectVisibleOptions(root){return Array.from(root?.querySelectorAll('.cselect-opt')||[]).filter(option=>option.offsetParent!==null&&option.getAttribute('aria-disabled')!=='true')},
  clearSelectHighlights(root=null){(root||document).querySelectorAll('.cselect-opt.highlighted,[data-highlighted="true"]').forEach(option=>{option.classList.remove('highlighted');option.removeAttribute('data-highlighted')})},
  highlightedSelectOption(root){const option=root?.querySelector('.cselect-opt.highlighted,[data-highlighted="true"]');return option&&this.selectVisibleOptions(root).includes(option)?option:null},
  setSelectHighlight(root,index){const options=this.selectVisibleOptions(root);if(!options.length)return;const normalized=(index+options.length)%options.length;this.clearSelectHighlights(root);const option=options[normalized];option.classList.add('highlighted');option.setAttribute('data-highlighted','true');option.scrollIntoView({block:'nearest'})},
  syncSelectHighlight(root,mode='active'){const targetRoot=root?.isConnected?root:document.querySelector('.cselect.open');const options=this.selectVisibleOptions(targetRoot);if(!options.length)return;let option=this.highlightedSelectOption(targetRoot);if(!option){option=mode==='last'?options[options.length-1]:targetRoot.querySelector('.cselect-opt.active');if(!options.includes(option))option=options[0]}this.setSelectHighlight(targetRoot,options.indexOf(option))},
  queueSelectHighlight(root,mode='active'){setTimeout(()=>this.syncSelectHighlight(root,mode),0)},
  moveSelectHighlight(root,delta){const options=this.selectVisibleOptions(root);if(!options.length)return;const current=this.highlightedSelectOption(root)||root.querySelector('.cselect-opt.active');const currentIndex=options.includes(current)?options.indexOf(current):-1;this.setSelectHighlight(root,currentIndex+delta)},
  handleSelectKeydown(event){const target=event.target;if(!target?.closest)return;const button=target.closest('.cselect-btn');if(!button)return;const root=button.closest('.cselect');if(!root)return;const key=event.key;const open=root.classList.contains('open');if(key==='Escape'){event.preventDefault();this.closeSelect(root);button.focus();return}if(!['ArrowDown','ArrowUp','Home','End','Enter',' ','Spacebar'].includes(key))return;event.preventDefault();if(!open){button.click();this.queueSelectHighlight(root,key==='ArrowUp'||key==='End'?'last':'active');return}if(key==='ArrowDown'){this.moveSelectHighlight(root,1);return}if(key==='ArrowUp'){this.moveSelectHighlight(root,-1);return}if(key==='Home'){this.setSelectHighlight(root,0);return}if(key==='End'){const options=this.selectVisibleOptions(root);this.setSelectHighlight(root,options.length-1);return}const option=this.highlightedSelectOption(root)||root.querySelector('.cselect-opt.active')||this.selectVisibleOptions(root)[0];if(option){option.click();this.clearSelectHighlights(root)}},
  selectOpt(k,model,val){this[model]=val;this.openSelect=null},

  async loadModels(){this.modelError='';try{const r=await fetch('/v1/models');const d=await r.json();this.models=d.data||[];if(!this.model&&this.models.length)this.model=this.models[0].id;this.applyModelCapabilities();this.ensureImageDefaults()}catch(e){this.modelError='模型列表加载失败'}},
  get selectedModel(){return this.models.find(m=>m.id===this.model)||{}},
  get selectedCaps(){return this.selectedModel.capabilities||{}},
  get imageModels(){return this.models.filter(m=>m.capabilities?.image_output)},
  get selectedImageModel(){return this.models.find(m=>m.id===this.imageModel)||this.imageModels[0]||{}},
  get imageGenerationMeta(){return this.selectedImageModel.image_generation||{}},
  get imageParameters(){return this.imageGenerationMeta.parameters||{}},
  get imageSizes(){return this.imageGenerationMeta.sizes||[]},
  get imageSizeValues(){return this.imageParameters.size?.enum||this.imageSizes.map(size=>size.size)},
  get imageCountMeta(){return this.imageParameters.n||{}},
  get imageCountMin(){return Number(this.imageCountMeta.minimum??1)},
  get imageCountMax(){return Number(this.imageCountMeta.maximum??10)},
  get imageCountDefault(){return Number(this.imageCountMeta.default??this.imageGenerationMeta.defaults?.n??1)},
  get imageCountHint(){return `${this.imageCountMin}-${this.imageCountMax}，默认 ${this.imageCountDefault}`},
  get imageResponseFormats(){return this.imageParameters.response_format?.enum||this.imageGenerationMeta.response_formats||[]},
  get imageDefaultResponseFormat(){return this.imageParameters.response_format?.default||this.imageGenerationMeta.defaults?.response_format||'b64_json'},
  get imageResponseFormat(){const formats=this.imageResponseFormats;return formats.includes('url')?'url':formats[0]||this.imageDefaultResponseFormat||'url'},
  get imageFormatLabel(){const formats=this.imageResponseFormats;return formats.length?formats.join(' / '):this.imageResponseFormat},
  get selectedHistoryItems(){return this.imageHistory.filter(item=>this.isHistorySelected(item))},
  get selectedHistoryCount(){return this.selectedHistoryItems.length},
  get allHistorySelected(){return !!this.imageHistory.length&&this.selectedHistoryCount===this.imageHistory.length},
  get activeImageSession(){return this.imageSessions.find(item=>item.id===this.activeImageSessionId)||{}},
  get imageEditReferences(){return [...(this.imageBaseImage?[{...this.imageBaseImage,reference_role:'base'}]:[]),...this.imageReferences.map(item=>({...item,reference_role:item.reference_role||'reference'}))]},
  get imageReferenceCount(){return this.imageEditReferences.length},
  get imageActionLabel(){if(this.imageBusy)return this.imageReferenceCount?'编辑中':'生成中';return this.imageReferenceCount?'发送编辑':'生成图片'},
  get imageRunSummary(){return `${this.imageSize} · ${this.imageCount||this.imageCountDefault} 张 · ${this.imageResponseFormat}`},
  get imageSubmitHint(){if(!this.imageModel)return'先选择可用的图像模型。';if(!this.imagePrompt.trim())return'输入提示词后即可开始生成。';return this.imageReferenceCount?'将提示词和素材一起发送，生成新的编辑结果。':'将根据提示词生成一组全新图片。'},
  get imageCanSubmit(){return !this.imageBusy&&!!this.imagePrompt.trim()&&!!this.imageModel},
  cap(k){return this.selectedCaps[k]===true},
  controlAvailable(k){if(!this.model)return false;if(k==='thinking')return this.cap('thinking');if(k==='search')return this.cap('search');if(k==='stream')return this.cap('streaming');if(k==='safety')return this.selectedCaps.safety_settings!==false;if(['temperature','top_p','max_tokens'].includes(k))return this.cap('text_output')&&!this.cap('image_output');return true},
  get acceptedFileTypes(){return this.selectedCaps.file_input_mime_types||[]},
  get chatFileAccept(){return this.acceptedFileTypes.length?this.acceptedFileTypes.join(','):''},
  get chatFileUploadEnabled(){return !!this.model&&this.selectedCaps.file_input===true&&!this.busy},
  get chatHasUnsupportedFiles(){return this.chatFiles.length>0&&this.selectedCaps.file_input!==true},
  get chatCanSend(){return !this.busy&&!!this.model&&(!!this.draft.trim()||this.chatFiles.length>0)&&!this.chatHasUnsupportedFiles},
  applyModelCapabilities(){if(!this.controlAvailable('thinking'))this.cfg.thinking='off';if(!this.controlAvailable('search'))this.cfg.search='off';if(!this.controlAvailable('stream'))this.cfg.stream='off';if(!this.controlAvailable('safety'))this.cfg.safety='on'},
  selectModel(id){this.model=id;this.openSelect=null;this.applyModelCapabilities();this.chatFileError=this.chatHasUnsupportedFiles?'当前模型不支持文件输入':''},
  ensureImageDefaults(){if(!this.imageModels.length){this.imageModel='';return}if(!this.imageModel||!this.imageModels.some(model=>model.id===this.imageModel))this.imageModel=this.imageModels[0].id;const defaultSize=this.imageSizeValues.includes(this.imageGenerationMeta.defaults?.size)?this.imageGenerationMeta.defaults.size:this.imageSizes[0]?.size;if(this.imageSizes.length&&!this.imageSizes.some(size=>size.size===this.imageSize))this.imageSize=defaultSize||'1024x1024';if(!this.imageCount)this.imageCount=this.imageCountDefault;this.normalizeImageCount()},
  selectImageModel(id){this.imageModel=id;this.openSelect=null;this.ensureImageDefaults()},
  async loadStats(){try{const r=await fetch('/stats');const d=await r.json();this.stats=d.models||{};this.statsTotals=d.totals||{}}catch(e){}},
  async fetchJson(url,opts){const r=await fetch(url,opts);let d=null;try{d=await r.json()}catch(e){}if(!r.ok){const detail=d?.detail;const msg=typeof detail==='string'?detail:(detail?.message||d?.error?.message||detail?.error?.message||(detail?JSON.stringify(detail):r.statusText||`HTTP ${r.status}`));const err=new Error(msg);err.status=r.status;throw err}return d},
  errMsg(e,fallback){return e?.message||fallback},
  async refreshAccountData(){await Promise.all([this.loadAccounts(),this.loadRotation()])},
  async loadAccounts(){this.accountsLoading=true;this.accountsError='';this.activeAccountNote='';try{this.accounts=await this.fetchJson('/accounts')||[]}catch(e){this.accounts=[];this.accountsError='账号列表加载失败：'+this.errMsg(e,'请求失败')}try{const a=await this.fetchJson('/accounts/active');this.activeId=a?.id||'';this.activeAccount=a||{}}catch(e){this.activeId='';this.activeAccount={};this.activeAccountNote=e.status===404?'当前没有激活账号':'活跃账号加载失败：'+this.errMsg(e,'请求失败')}finally{this.accountsLoading=false}},
  async loadRotation(){this.rotationError='';try{const d=await this.fetchJson('/rotation');this.rotationMode=d?.mode||'round_robin';this.rotCfg.mode=d?.mode||'round_robin';this.rotCfg.cooldown=d?.cooldown_seconds||60;this.rotationAccounts=d?.accounts||{}}catch(e){this.rotationError='轮询信息加载失败：'+this.errMsg(e,'请求失败')}},

  get accountRows(){return this.accounts.map(a=>({...(this.rotationAccounts[a.id]||{}),...a}))},
  get accountCount(){return this.accounts.length},
  get activeLabel(){return this.activeAccount.email||this.activeAccount.name||this.activeId||'暂无'},
  get loginBusy(){return this.loginStarting||this.loginSession.status==='pending'},
  get totalReqs(){return this.statsTotals.requests??Object.values(this.stats).reduce((s,v)=>s+(v.requests||0),0)},
  get totalRL(){return this.statsTotals.rate_limited??Object.values(this.stats).reduce((s,v)=>s+(v.rate_limited||0),0)},
  get healthyAccountCount(){return this.accountRows.filter(a=>(a.health_status||'unknown')==='healthy'&&a.is_available!==false).length},
  get premiumAccountCount(){return this.accountRows.filter(a=>['pro','ultra'].includes(a.tier)).length},
  get coolingAccountCount(){return this.accountRows.filter(a=>['rate_limited','isolated','expired','missing_auth','error'].includes(a.health_status)||a.is_available===false).length},
  get totalAccountRequests(){return this.accountRows.reduce((s,a)=>s+(a.requests||0),0)},
  get totalAccountImageUsage(){return this.accountRows.reduce((s,a)=>s+(a.image_total||0),0)},
  get accountImageSizeTotals(){const totals={};this.accountRows.forEach(a=>Object.entries(a.image_sizes||{}).forEach(([size,count])=>{totals[size]=(totals[size]||0)+count}));return Object.entries(totals).sort((a,b)=>b[1]-a[1])},

  accountLabel(a){return a?.email||a?.name||a?.id||'未知账号'},
  tierLabel(t){return t==='ultra'?'Ultra':t==='pro'?'Pro':'Free'},
  rotationLabel(m){return m==='round_robin'?'顺序轮询':m==='lru'?'LRU':m==='least_rl'?'最少限流':m==='exhaustion'?'耗尽模式':m||'未知'},
  rotationHint(m){return m==='exhaustion'?'当前账号持续使用到限流或不可用':m==='lru'?'优先选择最久未使用账号':m==='least_rl'?'优先选择限流次数最少账号':'按账号池顺序分配请求'},
  imageSizeEntries(a){return Object.entries(a?.image_sizes||{}).sort((x,y)=>y[1]-x[1])},
  healthLabel(s){return {healthy:'健康',rate_limited:'冷却中',isolated:'已隔离',expired:'登录过期',missing_auth:'缺少凭证',error:'异常',unknown:'未知'}[s||'unknown']||s},
  healthClass(s){if(s==='healthy')return'badge-green';if(['rate_limited','isolated','expired','missing_auth','error'].includes(s))return'badge-red';return'badge-gray'},
  setAccountBusy(action,id,busy){const key=`${action}:${id}`;const next={...this.accountBusy};if(busy)next[key]=true;else delete next[key];this.accountBusy=next},
  isAccountBusy(action,id){return !!this.accountBusy[`${action}:${id}`]},
  isRowBusy(id){return this.isAccountBusy('activate',id)||this.isAccountBusy('rename',id)||this.isAccountBusy('delete',id)||this.isAccountBusy('health',id)||this.isAccountBusy('tier',id)},
  loginStatusText(){const s=this.loginSession.status;if(s==='pending')return'等待浏览器登录';if(s==='completed')return'登录完成';if(s==='failed')return'登录失败';return'未开始'},
  loginStatusClass(){const s=this.loginSession.status;if(s==='completed')return'notice-success';if(s==='failed')return'notice-error';return'notice-info'},
  async saveRotation(){if(this.savingRotation)return;this.savingRotation=true;try{await this.fetchJson('/rotation/mode',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mode:this.rotCfg.mode,cooldown_seconds:this.rotCfg.cooldown})});this.showToast('已保存');await this.loadRotation()}catch(e){this.showToast('保存失败：'+this.errMsg(e,'请求失败'))}finally{this.savingRotation=false}},
  async forceNext(){if(this.forcingNext)return;this.forcingNext=true;try{await this.fetchJson('/rotation/next',{method:'POST'});this.showToast('已切换账号');await this.refreshAccountData()}catch(e){this.showToast('切换失败：'+this.errMsg(e,'请求失败'))}finally{this.forcingNext=false}},
  async activateAccount(id){if(this.isAccountBusy('activate',id))return;this.setAccountBusy('activate',id,true);try{await this.fetchJson(`/accounts/${encodeURIComponent(id)}/activate`,{method:'POST'});this.showToast('已激活');await this.refreshAccountData()}catch(e){this.showToast('激活失败：'+this.errMsg(e,'请求失败'))}finally{this.setAccountBusy('activate',id,false)}},
  async testAccount(a){const id=a.id;if(this.isAccountBusy('health',id))return;this.setAccountBusy('health',id,true);try{const d=await this.fetchJson(`/accounts/${encodeURIComponent(id)}/test`,{method:'POST'});this.showToast(d?.ok?'账号检查通过':'账号检查未通过：'+(d?.reason||d?.status||'未知原因'));await this.refreshAccountData()}catch(e){this.showToast('检查失败：'+this.errMsg(e,'请求失败'))}finally{this.setAccountBusy('health',id,false)}},
  async updateTier(a,tier){const id=a.id;if(tier===a.tier||this.isAccountBusy('tier',id))return;this.setAccountBusy('tier',id,true);try{await this.fetchJson(`/accounts/${encodeURIComponent(id)}`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({tier})});this.showToast('账号等级已更新');await this.refreshAccountData()}catch(e){this.showToast('等级更新失败：'+this.errMsg(e,'请求失败'))}finally{this.setAccountBusy('tier',id,false)}},
  beginRename(a){this.renameId=a.id;this.renameDraft=a.name||a.email||'';this.deleteConfirmId=''},
  cancelRename(){this.renameId='';this.renameDraft=''},
  async renameAccount(a){const id=a.id;const name=this.renameDraft.trim();if(!name){this.showToast('名称不能为空');return}if(name===a.name){this.cancelRename();return}if(this.isAccountBusy('rename',id))return;this.setAccountBusy('rename',id,true);try{await this.fetchJson(`/accounts/${encodeURIComponent(id)}`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({name})});this.showToast('已重命名');this.cancelRename();await this.refreshAccountData()}catch(e){this.showToast('重命名失败：'+this.errMsg(e,'请求失败'))}finally{this.setAccountBusy('rename',id,false)}},
  requestDeleteAccount(a){this.deleteConfirmId=a.id;this.renameId='';this.renameDraft=''},
  cancelDelete(){this.deleteConfirmId=''},
  async deleteAccount(a){const id=a.id;if(this.isAccountBusy('delete',id))return;this.setAccountBusy('delete',id,true);try{await this.fetchJson(`/accounts/${encodeURIComponent(id)}`,{method:'DELETE'});this.showToast('已删除 '+this.accountLabel(a));this.deleteConfirmId='';await this.refreshAccountData()}catch(e){this.showToast('删除失败：'+this.errMsg(e,'请求失败'))}finally{this.setAccountBusy('delete',id,false)}},
  async exportCredentials(id=''){if(this.credentialExporting)return;this.credentialExporting=true;this.credentialError='';try{const url=id?`/accounts/${encodeURIComponent(id)}/export`:'/accounts/export';const d=await this.fetchJson(url);this.credentialExportText=JSON.stringify(d,null,2);this.showToast('凭证已导出到文本框')}catch(e){this.credentialError='导出失败：'+this.errMsg(e,'请求失败');this.showToast(this.credentialError)}finally{this.credentialExporting=false}},
  async importCredentials(){if(this.credentialImporting)return;this.credentialError='';let payload=null;try{payload=JSON.parse(this.credentialImportText)}catch(e){this.credentialError='导入失败：JSON 格式无效';this.showToast(this.credentialError);return}this.credentialImporting=true;try{const params=new URLSearchParams();const name=this.credentialImportName.trim();if(name)params.set('name',name);const qs=params.toString();const d=await this.fetchJson('/accounts/import'+(qs?`?${qs}`:''),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});this.showToast(`已导入 ${d?.count||0} 个账号`);this.credentialImportText='';this.credentialImportName='';await this.refreshAccountData()}catch(e){this.credentialError='导入失败：'+this.errMsg(e,'请求失败');this.showToast(this.credentialError)}finally{this.credentialImporting=false}},
  clearLoginPoll(){if(this.loginPollTimer){clearTimeout(this.loginPollTimer);this.loginPollTimer=null}},
  async addAccount(){if(this.loginBusy)return;this.loginStarting=true;this.clearLoginPoll();try{const d=await this.fetchJson('/accounts/login/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({})});if(!d?.session_id)throw new Error('登录会话缺少 session_id');this.loginSession={id:d.session_id,status:'pending',email:'',error:''};this.showToast('登录已开始');this.pollLoginStatus()}catch(e){this.loginSession={id:'',status:'failed',email:'',error:this.errMsg(e,'启动登录失败')};this.showToast('启动登录失败：'+this.loginSession.error)}finally{this.loginStarting=false}},
  async pollLoginStatus(){const id=this.loginSession.id;if(!id)return;try{const d=await this.fetchJson(`/accounts/login/status/${encodeURIComponent(id)}`);const status=d?.status||'pending';this.loginSession={id:d?.session_id||id,status,email:d?.email||'',error:d?.error||''};if(status==='completed'){this.clearLoginPoll();this.showToast('登录完成');await this.refreshAccountData();return}if(status==='failed'){this.clearLoginPoll();this.showToast('登录失败：'+(d?.error||'请重试'));return}this.clearLoginPoll();this.loginPollTimer=setTimeout(()=>this.pollLoginStatus(),2000)}catch(e){this.clearLoginPoll();this.loginSession={...this.loginSession,status:'failed',error:this.errMsg(e,'状态查询失败')};this.showToast('登录状态查询失败：'+this.loginSession.error)}},

  resizeTa(){const el=this.$refs.ta;if(!el)return;el.style.height='auto';el.style.height=Math.min(el.scrollHeight,200)+'px'},
  scrollDown(){setTimeout(()=>{const el=document.getElementById('chat-scroll');if(el)el.scrollTop=el.scrollHeight},50)},
  fileToDataUrl(file){return new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=()=>reject(reader.error||new Error('读取文件失败'));reader.readAsDataURL(file)})},
  mimeMatches(mime,pattern){if(!pattern)return false;const type=(mime||'application/octet-stream').toLowerCase();const allowed=String(pattern).toLowerCase();return allowed==='*/*'||allowed===type||(allowed.endsWith('/*')&&type.startsWith(allowed.slice(0,-1)))},
  fileAccepted(file){const accepted=this.acceptedFileTypes;if(!accepted.length)return true;const mime=file.type||'application/octet-stream';return accepted.some(pattern=>this.mimeMatches(mime,pattern))},
  fileSizeLabel(bytes){const n=Number(bytes)||0;if(n>=1024*1024)return`${(n/1024/1024).toFixed(1)} MB`;if(n>=1024)return`${Math.round(n/1024)} KB`;return`${n} B`},
  async attachChatFiles(event){this.chatFileError='';if(!this.selectedCaps.file_input){this.chatFileError='当前模型不支持文件输入';this.showToast(this.chatFileError);event.target.value='';return}const files=Array.from(event.target.files||[]);for(const file of files){const mime=file.type||'application/octet-stream';if(!this.fileAccepted(file)){this.chatFileError=`不支持的文件类型：${mime}`;continue}if(file.size>20*1024*1024){this.chatFileError='单个文件不能超过 20 MB';continue}try{const url=await this.fileToDataUrl(file);this.chatFiles.push({name:file.name||'upload',url,mime,size:file.size,isImage:mime.startsWith('image/')})}catch(error){this.chatFileError='文件读取失败'}}event.target.value='';if(this.chatFileError)this.showToast(this.chatFileError)},
  removeChatFile(index){this.chatFiles.splice(index,1)},

  async attachImageReferences(event){this.imageReferenceError='';const files=Array.from(event.target.files||[]);for(const file of files){if(!file.type.startsWith('image/'))continue;if(file.size>20*1024*1024){this.imageReferenceError='单张图片不能超过 20 MB';continue}try{const url=await this.fileToDataUrl(file);this.imageReferences.push({id:`upload-${Date.now()}-${Math.random().toString(16).slice(2)}`,name:file.name,url,path:'',prompt:file.name,source:'upload',reference_role:'reference',created:Math.floor(Date.now()/1000),mime_type:file.type,size_bytes:file.size})}catch(error){this.imageReferenceError='图片读取失败'}}event.target.value='';if(this.imageReferenceError)this.showToast(this.imageReferenceError)},
  imageReferenceKey(item){return String(item?.path||item?.url||item?.id||'')},
  pinImageReference(item,source='history'){const ref=this.lightweightImageItem(item);if(!ref){this.showToast('图片不可用');return}const key=this.imageReferenceKey(ref);if(this.imageReferences.some(existing=>this.imageReferenceKey(existing)===key)){this.showToast('参考图已存在');return}this.imageReferences.push({...ref,id:`ref-${Date.now()}-${Math.random().toString(16).slice(2)}`,source,reference_role:'reference'});this.showToast('已加入参考图')},
  pinSelectedHistory(){this.selectedHistoryItems.forEach(item=>this.pinImageReference(item,'history'));this.clearImageSelection()},
  removeImageReference(index){this.imageReferences.splice(index,1)},
  setBaseImage(item){const ref=this.lightweightImageItem(item);if(!ref){this.showToast('图片不可用');return}this.imageBaseImage={...ref,reference_role:'base',source:'base'};this.showToast('已设为下一轮基图')},
  clearBaseImage(){this.imageBaseImage=null},
  clearImageEditSession(){this.imagePrompt='';this.imageResults=[];this.imageError='';this.imageReferences=[];this.imageBaseImage=null;this.imageConversation=[];this.imageLastRequest=null;this.activeImageSessionId='';this.imageReferenceError='';this.imageSessionError='';this.imagePreview=null;this.clearImageSelection();this.showToast('已开启新会话')},
  async imageItemToRequestUrl(item){const url=this.imageUrl(item);if(!url)throw new Error('图片不可用');if(url.startsWith('data:'))return url;const requestPath=this.sameOriginRequestPath(url);const response=await fetch(requestPath||url);if(!response.ok)throw new Error(`图片读取失败：HTTP ${response.status}`);const blob=await response.blob();if(!blob.type.startsWith('image/'))throw new Error('图片内容不是有效图片');return await this.fileToDataUrl(blob)},
  async imageRequestImages(){const refs=this.imageEditReferences;const images=[];for(const ref of refs){images.push(await this.imageItemToRequestUrl(ref))}return images},

  async loadImageSessions(showLoading=true){if(showLoading)this.imageSessionLoading=true;this.imageSessionError='';try{const d=await this.fetchJson('/image-sessions');this.imageSessions=Array.isArray(d?.data)?d.data:[]}catch(error){this.imageSessions=[];this.imageSessionError='会话历史加载失败：'+this.errMsg(error,'请求失败')}finally{this.imageSessionLoading=false}},
  imageSessionImages(items){return (Array.isArray(items)?items:[]).map((item,index)=>this.lightweightImageItem(item,index)).filter(Boolean)},
  imageSessionConversation(){return this.imageConversation.map(turn=>({...turn,images:this.imageSessionImages(turn.images||[])}))},
  imageSessionTitle(prompt=''){const text=(prompt||this.imagePrompt||this.imageConversation.slice().reverse().find(turn=>turn.prompt)?.prompt||'').trim();return text?text.slice(0,80):'未命名图片会话'},
  imageSessionMeta(session){const parts=[session.model||'未知模型',session.size||'默认尺寸'];if(session.turn_count)parts.push(session.turn_count+' 轮');return parts.join(' · ')},
  imageSessionPayload(prompt=this.imagePrompt){const results=this.imageSessionImages(this.imageResults);const baseImage=this.imageBaseImage?this.lightweightImageItem(this.imageBaseImage):null;const references=this.imageSessionImages(this.imageReferences);const lastRequest=this.imageLastRequest?{...this.imageLastRequest,imageBaseImage:this.imageLastRequest.imageBaseImage?this.lightweightImageItem(this.imageLastRequest.imageBaseImage):null,imageReferences:this.imageSessionImages(this.imageLastRequest.imageReferences||[])}:null;return{id:this.activeImageSessionId||undefined,title:this.imageSessionTitle(prompt),prompt,model:this.imageModel,size:this.imageSize,count:this.imageCount,response_format:this.imageResponseFormat,results,base_image:baseImage,references,conversation:this.imageSessionConversation(),last_request:lastRequest}},
  async saveCurrentImageSession(prompt=this.imagePrompt){if(!this.imageResults.length&&!this.imageConversation.length)return;this.imageSessionSaving=true;this.imageSessionError='';try{const payload=this.imageSessionPayload(prompt);const updating=!!this.activeImageSessionId;const url=updating?`/image-sessions/${encodeURIComponent(this.activeImageSessionId)}`:'/image-sessions';const session=await this.fetchJson(url,{method:updating?'PUT':'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});this.activeImageSessionId=session?.id||this.activeImageSessionId;await this.loadImageSessions(false)}catch(error){this.imageSessionError='会话保存失败：'+this.errMsg(error,'请求失败');this.showToast(this.imageSessionError)}finally{this.imageSessionSaving=false}},
  applyImageSession(session){this.activeImageSessionId=session.id||'';if(session.model)this.imageModel=session.model;this.ensureImageDefaults();if(session.size)this.imageSize=session.size;if(session.count)this.imageCount=session.count;this.normalizeImageCount();this.imagePrompt=session.prompt||'';this.imageResults=this.imageSessionImages(session.results||[]);this.imageBaseImage=session.base_image?this.lightweightImageItem(session.base_image):null;this.imageReferences=this.imageSessionImages(session.references||[]);this.imageConversation=Array.isArray(session.conversation)?session.conversation.map(turn=>({...turn,images:this.imageSessionImages(turn.images||[])})):[];this.imageLastRequest=session.last_request||null;this.imageError='';this.imageReferenceError='';this.imageSessionError='';this.imagePreview=null},
  async restoreImageSession(session){if(!session?.id||this.imageBusy)return;this.imageSessionError='';try{const data=await this.fetchJson(`/image-sessions/${encodeURIComponent(session.id)}`);this.applyImageSession(data);this.showToast('已恢复会话')}catch(error){this.imageSessionError='会话恢复失败：'+this.errMsg(error,'请求失败');this.showToast(this.imageSessionError)}},
  async deleteImageSession(session){if(!session?.id||this.imageSessionDeletingId)return;this.imageSessionDeletingId=session.id;this.imageSessionError='';try{await this.fetchJson(`/image-sessions/${encodeURIComponent(session.id)}`,{method:'DELETE'});if(this.activeImageSessionId===session.id)this.activeImageSessionId='';await this.loadImageSessions(false);this.showToast('已删除会话')}catch(error){this.imageSessionError='会话删除失败：'+this.errMsg(error,'请求失败');this.showToast(this.imageSessionError)}finally{this.imageSessionDeletingId=''}},

  async send(){const t=this.draft.trim();if((!t&&!this.chatFiles.length)||this.busy||!this.model)return;
    if(this.chatHasUnsupportedFiles){this.chatFileError='当前模型不支持文件输入';this.showToast(this.chatFileError);return}
    this.applyModelCapabilities();
    const files=this.chatFiles.map(file=>({...file}));
    const apiContent=files.length?[...(t?[{type:'text',text:t}]:[]),...files.map(file=>file.isImage?{type:'image_url',image_url:{url:file.url}}:{type:'file',file:{file_data:file.url,filename:file.name,mime_type:file.mime}})]:t;
    this.msgs.push({role:'user',content:t,files,images:files.filter(file=>file.isImage),apiContent});this.draft='';this.chatFiles=[];this.chatFileError='';this.busy=true;this.resizeTa();this.scrollDown();
    const body={model:this.model,messages:this.msgs.map(m=>({role:m.role,content:m.apiContent||m.content}))};
    if(this.controlAvailable('temperature')&&this.cfg.temperature!==1) body.temperature=this.cfg.temperature;
    if(this.controlAvailable('top_p')&&this.cfg.topP!==1) body.top_p=this.cfg.topP;
    if(this.controlAvailable('max_tokens')&&this.cfg.maxTokens!==8192) body.max_tokens=this.cfg.maxTokens;
    if(this.controlAvailable('stream')&&this.cfg.stream==='on') body.stream=true;
    if(this.controlAvailable('thinking')&&this.cfg.thinking!=='off') body.thinking=this.cfg.thinking;
    if(this.controlAvailable('search')&&this.cfg.search==='on') body.grounding=true;
    if(this.controlAvailable('safety')&&this.cfg.safety==='off') body.safety_off=true;
    const useStream=!!body.stream;

    try{const r=await fetch('/v1/chat/completions',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
      if(!r.ok){let e=r.statusText;try{const d=await r.json();if(d.detail)e=d.detail.message||JSON.stringify(d.detail);else if(d.error)e=d.error.message||JSON.stringify(d.error)}catch(x){};this.msgs.push({role:'assistant',content:'',error:`Error ${r.status}: ${e}`})}
      else if(useStream){
        const reader=r.body.getReader();const dec=new TextDecoder();this.msgs.push({role:'assistant',content:'',thinking:'',showThinking:false});const idx=this.msgs.length-1;let buf='';
        while(true){const{done,value}=await reader.read();if(done)break;buf+=dec.decode(value,{stream:true});const lines=buf.split('\n');buf=lines.pop();
          for(const ln of lines){if(ln.startsWith('data: ')&&ln!=='data: [DONE]'){try{const d=JSON.parse(ln.slice(6));const delta=d.choices?.[0]?.delta||{};
            const c=delta.content;if(c)this.msgs[idx].content+=c;
            const th=delta.reasoning_content||delta.thinking||delta.reasoning;if(th)this.msgs[idx].thinking+=th;
            if(delta.tool_calls)this.msgs[idx].content+='\n'+JSON.stringify(delta.tool_calls);
          }catch(e){}}}
          this.scrollDown()}
      }else{const d=await r.json();const msg=d.choices?.[0]?.message||{};
        this.msgs.push({role:'assistant',content:msg.content||'(无响应内容)',thinking:msg.reasoning_content||msg.thinking||msg.reasoning||'',showThinking:false})}}
    catch(e){this.msgs.push({role:'assistant',content:'',error:e.message})}
    finally{this.busy=false;this.scrollDown()}},

  loadImageHistory(){try{const stored=JSON.parse(localStorage.getItem('aistudio.imageHistory')||'[]');this.imageHistory=(Array.isArray(stored)?stored:[]).map((item,index)=>this.lightweightImageItem(item,index)).filter(Boolean).slice(0,24);this.pruneImageSelection();this.saveImageHistory()}catch(error){this.imageHistory=[];this.imageHistorySelection={}}},
  saveImageHistory(){try{localStorage.setItem('aistudio.imageHistory',JSON.stringify(this.imageHistory.map((item,index)=>this.lightweightImageItem(item,index)).filter(Boolean).slice(0,24)))}catch(error){this.imageHistoryError='历史保存失败：浏览器存储不可用'}},
  imageUrl(item){return item.url||((item.b64_json||item.b64)?`data:image/png;base64,${item.b64_json||item.b64}`:'')},
  openImagePreview(item){if(!this.imageUrl(item))return;this.imagePreview={...item};this.closeSelect()},
  closeImagePreview(){this.imagePreview=null},
  generatedImageUrl(path){return '/generated-images/'+String(path||'').split('/').filter(Boolean).map(encodeURIComponent).join('/')},
  pathFromGeneratedImageUrl(url){if(!url)return'';try{const parsed=new URL(url,window.location.origin);if(parsed.origin!==window.location.origin)return'';const prefix='/generated-images/';return parsed.pathname.startsWith(prefix)?decodeURIComponent(parsed.pathname.slice(prefix.length)):''}catch(error){return''}},
  sameOriginRequestPath(url){if(!url||String(url).startsWith('data:'))return'';try{const parsed=new URL(url,window.location.origin);return parsed.origin===window.location.origin?parsed.pathname+parsed.search:''}catch(error){return''}},
  lightweightImageItem(item,index=0){if(!item||typeof item!=='object')return null;const rawUrl=this.imageUrl(item);const path=item.path||this.pathFromGeneratedImageUrl(rawUrl);const url=rawUrl&&!rawUrl.startsWith('data:')?rawUrl:(path?this.generatedImageUrl(path):'');if(!url&&!path)return null;return{id:item.id||path||url,url,path,delete_url:item.delete_url||url,prompt:item.prompt||'',model:item.model||'',size:item.size||'',index:item.index||index+1,created:item.created||Math.floor(Date.now()/1000),revised_prompt:item.revised_prompt||'',mime_type:item.mime_type||'',size_bytes:item.size_bytes||0}},
  historyItemId(item){return String(item?.id||item?.path||item?.url||`${item?.created||0}-${item?.index||0}`)},
  isHistorySelected(item){return !!this.imageHistorySelection[this.historyItemId(item)]},
  toggleHistorySelection(item){const id=this.historyItemId(item);const next={...this.imageHistorySelection};if(next[id])delete next[id];else next[id]=true;this.imageHistorySelection=next},
  selectAllImageHistory(){const next={};this.imageHistory.forEach(item=>{next[this.historyItemId(item)]=true});this.imageHistorySelection=next},
  clearImageSelection(){this.imageHistorySelection={}},
  pruneImageSelection(){const valid=new Set(this.imageHistory.map(item=>this.historyItemId(item)));const next={};Object.keys(this.imageHistorySelection).forEach(id=>{if(valid.has(id))next[id]=true});this.imageHistorySelection=next},
  serverImageDeleteUrl(item){const explicit=this.sameOriginRequestPath(item?.delete_url||'');if(explicit&&item?.path)return explicit;const path=item?.path||this.pathFromGeneratedImageUrl(item?.delete_url||'')||this.pathFromGeneratedImageUrl(item?.url||'');if(path)return this.generatedImageUrl(path);return''},
  normalizeImageCount(){const count=Math.max(this.imageCountMin,Math.min(this.imageCountMax,Math.floor(Number(this.imageCount)||this.imageCountDefault)));this.imageCount=count;return count},
  async generateImage(){const prompt=this.imagePrompt.trim();if(!prompt||this.imageBusy)return;this.ensureImageDefaults();if(!this.imageModel){this.imageError='没有可用的图像模型';return}const count=this.normalizeImageCount();this.imageBusy=true;this.imageError='';this.imageReferenceError='';this.imageHistoryError='';this.imageResults=[];const referenceSnapshot=this.imageEditReferences.map(item=>({...item}));const body={model:this.imageModel,prompt,size:this.imageSize,n:count,response_format:this.imageResponseFormat};this.imageLastRequest={...body,imageBaseImage:this.imageBaseImage?{...this.imageBaseImage}:null,imageReferences:this.imageReferences.map(item=>({...item}))};try{const images=await this.imageRequestImages();if(images.length)body.images=images;const data=await this.fetchJson('/v1/images/generations',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});this.imageResults=(data.data||[]).map((item,index)=>({...item,url:this.imageUrl(item),prompt,model:this.imageModel,size:this.imageSize,index:index+1,created:data.created||Date.now()/1000}));const historyItems=this.imageResults.map((item,index)=>this.lightweightImageItem(item,index)).filter(Boolean);if(this.imageResults.length){this.imageHistory=[...historyItems,...this.imageHistory].slice(0,24);this.imageBaseImage={...historyItems[0],reference_role:'base',source:'generated'};this.imageConversation.push({role:'user',prompt,images:referenceSnapshot,created:Date.now()});this.imageConversation.push({role:'assistant',images:historyItems.map(item=>({...item})),created:Date.now()});this.pruneImageSelection();this.saveImageHistory();await this.saveCurrentImageSession(prompt);this.imagePrompt=''}else{this.imageError='没有返回图片'}this.showToast(`${images.length?'编辑':'生成'}完成：${this.imageResults.length} 张`)}catch(error){this.imageError=this.errMsg(error,'生成失败');this.showToast('生成失败：'+this.imageError)}finally{this.imageBusy=false}},
  retryLastImage(){if(!this.imageLastRequest||this.imageBusy)return;this.imagePrompt=this.imageLastRequest.prompt||this.imagePrompt;this.imageModel=this.imageLastRequest.model||this.imageModel;this.imageSize=this.imageLastRequest.size||this.imageSize;this.imageCount=this.imageLastRequest.n||this.imageCount;this.imageBaseImage=this.imageLastRequest.imageBaseImage||this.imageBaseImage;this.imageReferences=(this.imageLastRequest.imageReferences||this.imageReferences).map(item=>({...item}));this.generateImage()},
  retryImage(item){this.imagePrompt=item.prompt||this.imagePrompt;this.imageModel=item.model||this.imageModel;this.imageSize=item.size||this.imageSize;this.setBaseImage(item);this.generateImage()},
  imageFileExtension(item){const mime=(item?.mime_type||'').toLowerCase();if(mime.includes('jpeg')||mime.includes('jpg'))return'jpg';if(mime.includes('webp'))return'webp';if(mime.includes('gif'))return'gif';const url=this.imageUrl(item).split('?')[0];const ext=url.match(/\.([a-z0-9]{2,5})$/i);return ext?ext[1].toLowerCase():'png'},
  downloadImage(item,position=0){const url=this.imageUrl(item);if(!url)return;const a=document.createElement('a');a.href=url;a.download=`aistudio-${item.index||position||Date.now()}.${this.imageFileExtension(item)}`;document.body.appendChild(a);a.click();a.remove()},
  downloadSelectedImages(){const items=this.selectedHistoryItems;if(!items.length)return;items.forEach((item,index)=>setTimeout(()=>this.downloadImage(item,index+1),index*120))},
  async deleteServerImage(item){const url=this.serverImageDeleteUrl(item);if(!url)return;await this.fetchJson(url,{method:'DELETE'})},
  async deleteImageItems(items){if(this.imageHistoryDeleting)return;const unique=[];const seen=new Set();items.forEach(item=>{const id=this.historyItemId(item);if(!seen.has(id)){seen.add(id);unique.push(item)}});if(!unique.length)return;this.imageHistoryDeleting=true;this.imageHistoryError='';const deletedIds=[];const failed=[];for(const item of unique){try{await this.deleteServerImage(item);deletedIds.push(this.historyItemId(item))}catch(error){failed.push({item,error})}}if(deletedIds.length){const removed=new Set(deletedIds);this.imageHistory=this.imageHistory.filter(item=>!removed.has(this.historyItemId(item)));this.imageResults=this.imageResults.filter(item=>!removed.has(this.historyItemId(item)));const next={...this.imageHistorySelection};deletedIds.forEach(id=>delete next[id]);this.imageHistorySelection=next;this.saveImageHistory()}if(failed.length){this.imageHistoryError=`删除失败 ${failed.length} 张：${this.errMsg(failed[0].error,'请求失败')}`;this.showToast(this.imageHistoryError)}else{this.showToast(`已删除 ${deletedIds.length} 张`)}this.imageHistoryDeleting=false},
  deleteHistoryImage(item){this.deleteImageItems([item])},
  deleteSelectedImages(){this.deleteImageItems(this.selectedHistoryItems)},
  clearImageHistory(){this.deleteImageItems([...this.imageHistory])},
  fmtImageTime(value){if(!value)return'-';try{return new Date(typeof value==='number'?value*1000:value).toLocaleString()}catch(error){return'-'}},

  fmtDate(s){if(!s)return'-';try{return new Date(s).toLocaleString()}catch(e){return s}}
}}
