import test from 'node:test';
import assert from 'node:assert/strict';
import {buildTrend,formatAxisDate,formatExtractionDate,parseExtractionDate} from '../src/trendData.js';

test('raggruppa i colori per data e mostra la media senza perdere il file',()=>{
 const result=buildTrend([
  {scanned_at:'2026-02-05T11:12:13',price_eur:200,filename:'b.xlsx'},
  {scanned_at:'2025-01-03T09:15:20',price_eur:80,filename:'a.xlsx'},
  {scanned_at:'2025-01-03T09:15:20',price_eur:120,filename:'a.xlsx'},
  {scanned_at:'non valida',price_eur:10},
 ]);
 assert.equal(result.length,2); assert.equal(result[0].value,100); assert.equal(result[0].count,2);
 assert.deepEqual(result[0].files,['a.xlsx']); assert.ok(result[0].time<result[1].time);
 assert.match(formatAxisDate(result[0].time),/03.*gen.*2025/i);
 assert.match(formatExtractionDate(result[0].time),/09:15:20/);
});

test('scarta dati e date non validi e mantiene il fuso esplicito',()=>{
 assert.equal(parseExtractionDate(''),null);
 assert.equal(buildTrend([{scanned_at:'2026-01-01T12:00:00',price_eur:null}]).length,0);
 assert.equal(parseExtractionDate('2026-01-01T12:00:00+01:00'),Date.parse('2026-01-01T11:00:00Z'));
});
