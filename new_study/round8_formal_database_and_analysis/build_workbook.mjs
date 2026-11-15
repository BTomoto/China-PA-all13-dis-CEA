import fs from 'node:fs/promises';
import path from 'node:path';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
const moduleRoot=process.env.ARTIFACT_NODE_MODULES || path.join(process.env.USERPROFILE,'.cache','codex-runtimes','codex-primary-runtime','dependencies','node','node_modules');
const resolve=createRequire(path.join(moduleRoot,'_resolve.cjs'));
const {Workbook,SpreadsheetFile}=await import(pathToFileURL(resolve.resolve('@oai/artifact-tool')).href);
const root=path.resolve(process.argv[2]);
const manifest=JSON.parse(await fs.readFile(path.join(root,'runtime','workbook_payload.json'),'utf8'));
const wb=Workbook.create();
const sheetMap={};
for(const item of manifest){
 const sh=wb.worksheets.add(item.sheet);sheetMap[item.sheet]=item.csv;
 const data=JSON.parse(await fs.readFile(path.join(root,'runtime',item.payload),'utf8'));
 sh.getRangeByIndexes(0,0,1,data.columns.length).values=[data.columns];
 for(let start=0;start<data.rows.length;start+=1000){const chunk=data.rows.slice(start,start+1000);sh.getRangeByIndexes(start+1,0,chunk.length,data.columns.length).values=chunk;}
 sh.showGridLines=false;sh.freezePanes.freezeRows(1);
 sh.getRangeByIndexes(0,0,data.rows.length+1,data.columns.length).format.font={name:'Arial',size:10};
 sh.getRangeByIndexes(0,0,1,data.columns.length).format={fill:'#334b61',font:{bold:true,color:'#ffffff'},wrapText:true,rowHeight:42};
 sh.getRangeByIndexes(0,0,data.rows.length+1,data.columns.length).format.columnWidth=23;
 for(let c=0;c<data.columns.length;c++){
  if(['val','population','p_inactive','p_active','lower','upper','benefit','attributable_B0'].includes(data.columns[c]))sh.getRangeByIndexes(1,c,data.rows.length,1).setNumberFormat('0.000000');
 }
 console.log(item.sheet,data.rows.length);
}
wb.recalculate();
const inspect=await wb.inspect({kind:'region',sheetId:manifest[0].sheet,range:'A1:G5',maxChars:1800});
await fs.writeFile(path.join(root,'logs','workbook_inspection.json'),JSON.stringify(inspect,null,2));
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!|#SPILL!',options:{useRegex:true,maxResults:20},maxChars:2000});
await fs.writeFile(path.join(root,'logs','workbook_error_scan.json'),JSON.stringify(errors,null,2));
for(const item of manifest){
 const preview=await wb.render({sheetName:item.sheet,range:'A1:F6',scale:1,format:'png'});
 await fs.writeFile(path.join(root,'runtime',item.sheet+'.png'),new Uint8Array(await preview.arrayBuffer()));
}
const output=await SpreadsheetFile.exportXlsx(wb);await output.save(path.join(root,'database','New_study_formal_database_v1.xlsx'));
await fs.writeFile(path.join(root,'logs','workbook_sheets.json'),JSON.stringify(sheetMap,null,2));
console.log('Workbook exported');
