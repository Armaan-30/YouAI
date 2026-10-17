// Some Windows redirected/encrypted folders reject same-directory rename with EXDEV.
// Keep the fallback confined to the builder's extracted download cache.
const fs=require('node:fs/promises'),path=require('node:path');
const cache=path.resolve(process.env.LOCALAPPDATA,'electron-builder','Cache');
const rename=fs.rename.bind(fs);
fs.rename=async(from,to)=>{
 try{return await rename(from,to);}catch(error){
  const source=path.resolve(String(from)),target=path.resolve(String(to));
  const allowed=(source.startsWith(cache+path.sep)&&target.startsWith(cache+path.sep)) || target===path.resolve(__dirname,'../dist/win-unpacked');
  if(!['EXDEV','EPERM'].includes(error.code)||!allowed||source!==target+'.tmp')throw error;
  await fs.cp(source,target,{recursive:true,errorOnExist:true,force:false});
 }
};
(async()=>{
 await require('electron-builder').build({targets:require('electron-builder').Platform.WINDOWS.createTarget('nsis')});
})().catch(error=>{console.error(error.message);process.exitCode=1;});
