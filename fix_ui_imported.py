import sys

filepath = './financeiro-frontend/src/app/despesas/page.tsx'
with open(filepath, 'r') as f:
    lines = f.readlines()

new_lines = []
in_main = False
for line in lines:
    new_lines.append(line)
    if "</div>" in line and "Nova Despesa" in "".join(lines[lines.index(line)-10:lines.index(line)]):
        # Add imported section right after the header
        new_lines.append("""
      {/* Seção de Importações Pendentes */}
      {importedDespesas.length > 0 && (
          <div className="bg-amber-50 border border-amber-200 rounded-xl shadow-sm p-6 mb-6">
              <h2 className="text-lg font-bold text-amber-900 mb-4 flex items-center gap-2">
                  <AlertCircle size={20} />
                  Despesas Importadas Pendentes de Categorização ({importedDespesas.length})
              </h2>
              <div className="space-y-4">
                  {importedDespesas.map((item, index) => (
                      <div key={item._tempId} className="bg-white border border-amber-100 rounded-lg p-4 shadow-sm flex flex-col gap-4">
                          <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                              <div className="flex-1">
                                  <div className="text-xs text-slate-500 font-mono mb-1">{item.data_transacao}</div>
                                  <div className="font-semibold text-slate-900">{item.descricao_original}</div>
                              </div>
                              <div className="font-mono font-bold text-rose-600 text-lg">
                                  - {Number(item.valor).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
                              </div>
                              <div className="w-full md:w-64">
                                  <select
                                      className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-sm"
                                      value={item.categoria_sugerida_id || ''}
                                      onChange={(e) => {
                                          const newImported = [...importedDespesas];
                                          newImported[index].categoria_sugerida_id = e.target.value;
                                          setImportedDespesas(newImported);
                                      }}
                                  >
                                      <option value="">Selecione a categoria...</option>
                                      {categoriasPendentes.map(c => (
                                          <option key={c.id} value={c.id}>{c.nome}</option>
                                      ))}
                                  </select>
                              </div>
                              <div className="flex gap-2 w-full md:w-auto">
                                  <button onClick={() => toggleImportedExpanded(index)} className="px-3 py-2 text-sm font-medium border border-slate-300 text-slate-700 rounded-lg hover:bg-slate-50 transition">
                                      Rateio ({item.rateios.length})
                                  </button>
                                  <button onClick={() => salvarImportada(index)} className="px-4 py-2 text-sm font-medium bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition">
                                      Salvar
                                  </button>
                              </div>
                          </div>

                          {/* Sanfona de Rateio */}
                          {item.expanded && (
                              <div className="pt-4 border-t border-slate-100 bg-slate-50/50 p-4 rounded-lg mt-2">
                                  <div className="flex justify-between items-center mb-4">
                                      <h3 className="text-sm font-semibold text-slate-700">Divisão da Despesa (Rateio)</h3>
                                      <button onClick={() => addImportedRateio(index)} className="text-xs text-indigo-600 font-medium hover:underline">+ Adicionar Linha</button>
                                  </div>

                                  {item.rateios.length === 0 ? (
                                      <p className="text-xs text-slate-500">Nenhum rateio configurado. O valor total irá para a categoria principal.</p>
                                  ) : (
                                      <div className="space-y-3">
                                          {item.rateios.map((r: any, rIdx: number) => (
                                              <div key={rIdx} className="grid grid-cols-1 md:grid-cols-4 gap-3">
                                                  <input
                                                      type="text"
                                                      placeholder="Descrição específica"
                                                      className="col-span-2 text-sm border border-slate-300 rounded px-3 py-2"
                                                      value={r.descricao}
                                                      onChange={(e) => updateImportedRateio(index, rIdx, 'descricao', e.target.value)}
                                                  />
                                                  <input
                                                      type="number"
                                                      step="0.01"
                                                      placeholder="Valor R$"
                                                      className="text-sm border border-slate-300 rounded px-3 py-2"
                                                      value={r.valor}
                                                      onChange={(e) => updateImportedRateio(index, rIdx, 'valor', e.target.value)}
                                                  />
                                                  <div className="flex gap-2">
                                                      <select
                                                          className="w-full text-sm border border-slate-300 rounded px-3 py-2"
                                                          value={r.categoria_id}
                                                          onChange={(e) => updateImportedRateio(index, rIdx, 'categoria_id', e.target.value)}
                                                      >
                                                          <option value="">(Usar principal)</option>
                                                          {categoriasPendentes.map(c => (
                                                              <option key={c.id} value={c.id}>{c.nome}</option>
                                                          ))}
                                                      </select>
                                                      <button
                                                          onClick={() => {
                                                              const newImported = [...importedDespesas];
                                                              newImported[index].rateios.splice(rIdx, 1);
                                                              setImportedDespesas(newImported);
                                                          }}
                                                          className="text-rose-500 hover:bg-rose-50 px-2 rounded"
                                                      >
                                                          <X size={16} />
                                                      </button>
                                                  </div>
                                              </div>
                                          ))}
                                      </div>
                                  )}
                              </div>
                          )}
                      </div>
                  ))}
              </div>
          </div>
      )}
""")

with open(filepath, 'w') as f:
    f.writelines(new_lines)
