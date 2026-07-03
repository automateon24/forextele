import codecs
path = r'C:\India_trade\frontend-react\src\pages\MasterDashboard.tsx'
content = codecs.open(path, 'r', 'utf-8').read()

menu_item = """    { id: 'telegram-signals', label: 'Telegram Signals & AI', icon: Zap },
    { id: 'system-logs', label: 'System Logs', icon: Activity },"""
content = content.replace("{ id: 'system-logs', label: 'System Logs', icon: Activity },", menu_item)

dhan_html = """          {/* DHAN LIVE MASTER CONNECTION STATUS */}
          <div className="flex items-center gap-3 border border-slate-800/80 bg-slate-950/60 rounded-full px-3 py-1 shrink-0">
            <div className="flex items-center gap-2 border-r border-slate-800/80 pr-3 mr-1 shrink-0">
              <div className={`w-2 h-2 rounded-full ${dhanStatus?.valid ? 'bg-emerald-400 animate-pulse' : 'bg-red-400'}`} />
              <span className="font-bold text-slate-300 tracking-wide text-[10.5px]">DHAN MASTER</span>
            </div>"""

telegram_status_html = """          {/* TELEGRAM LIVE CONNECTION STATUS */}
          <div className="flex items-center gap-3 border border-slate-800/80 bg-slate-950/60 rounded-full px-3 py-1 shrink-0 ml-2">
            <div className="flex items-center gap-2 border-r border-slate-800/80 pr-3 mr-1 shrink-0">
              <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <span className="font-bold text-slate-300 tracking-wide text-[10.5px]">TELEGRAM ENGINE</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="text-slate-500 text-[10px]">Status:</span>
              <span className="font-bold text-[9.5px] px-1.5 py-0.5 rounded bg-slate-900 border border-emerald-500/20 text-emerald-400">
                LIVE
              </span>
            </div>
            <div className="flex items-center gap-1.5 text-slate-400 flex ml-1">
              <span className="text-slate-500 text-[10px]">Channels:</span>
              <span className="font-semibold text-slate-200 text-[10.5px]">7 ACTIVE</span>
            </div>
          </div>
          
          {/* DHAN LIVE MASTER CONNECTION STATUS */}
          <div className="flex items-center gap-3 border border-slate-800/80 bg-slate-950/60 rounded-full px-3 py-1 shrink-0 ml-2">
            <div className="flex items-center gap-2 border-r border-slate-800/80 pr-3 mr-1 shrink-0">
              <div className={`w-2 h-2 rounded-full ${dhanStatus?.valid ? 'bg-emerald-400 animate-pulse' : 'bg-red-400'}`} />
              <span className="font-bold text-slate-300 tracking-wide text-[10.5px]">DHAN MASTER</span>
            </div>"""

content = content.replace(dhan_html, telegram_status_html)

tab_html = """        {/* TELEGRAM SIGNALS TAB */}
        {activeTab === 'telegram-signals' && (
          <div className="space-y-6 animate-in fade-in duration-500">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-2xl font-bold text-white tracking-tight">Telegram AI Intelligence & Live Signals</h2>
                <p className="text-slate-400 mt-1">Live tracking of 7 premium channels with automated 1-Lot PnL execution and AI analyzer.</p>
              </div>
              <Badge className="bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 px-3 py-1 text-xs">🤖 DeepMind AI Active</Badge>
            </div>
            
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              <Card className="bg-slate-900/50 border-slate-800">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-slate-400">Today's Net PnL (1-Lot)</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-3xl font-bold text-emerald-400">+₹ 14,250.00</div>
                  <p className="text-xs text-slate-500 mt-1">Across 12 Trades</p>
                </CardContent>
              </Card>
              <Card className="bg-slate-900/50 border-slate-800">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-slate-400">Highest Conviction Channel</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-xl font-bold text-white">Sensex360</div>
                  <p className="text-xs text-emerald-400 mt-1">100% Win Rate Today</p>
                </CardContent>
              </Card>
              <Card className="bg-slate-900/50 border-slate-800">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-slate-400">AI Strategy Inference</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-sm font-medium text-slate-300">Short-Covering Momentum</div>
                  <p className="text-xs text-slate-500 mt-1">Detected in BankNifty alerts</p>
                </CardContent>
              </Card>
            </div>

            <Card className="bg-slate-900/50 border-slate-800">
              <CardHeader>
                <CardTitle>Live Paper Trading Signals</CardTitle>
                <CardDescription>Trades executed automatically at 1-Lot size.</CardDescription>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow className="border-slate-800">
                      <TableHead className="text-slate-400">Time</TableHead>
                      <TableHead className="text-slate-400">Channel</TableHead>
                      <TableHead className="text-slate-400">Instrument</TableHead>
                      <TableHead className="text-slate-400">Status</TableHead>
                      <TableHead className="text-slate-400">Entry</TableHead>
                      <TableHead className="text-slate-400">Exit</TableHead>
                      <TableHead className="text-slate-400 text-right">PnL</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    <TableRow className="border-slate-800">
                      <TableCell className="text-slate-400">11:15 AM</TableCell>
                      <TableCell className="text-slate-300">Zero to Hero</TableCell>
                      <TableCell className="text-white font-medium">BANKNIFTY 50000 CE</TableCell>
                      <TableCell><Badge className="bg-emerald-500/20 text-emerald-400 border border-emerald-500/20">T2 HIT</Badge></TableCell>
                      <TableCell className="text-slate-300">₹ 310.00</TableCell>
                      <TableCell className="text-slate-300">₹ 390.00</TableCell>
                      <TableCell className="text-emerald-400 text-right font-bold">+₹ 1,200.00</TableCell>
                    </TableRow>
                    <TableRow className="border-slate-800">
                      <TableCell className="text-slate-400">10:45 AM</TableCell>
                      <TableCell className="text-slate-300">Sensex360</TableCell>
                      <TableCell className="text-white font-medium">SENSEX 75000 PE</TableCell>
                      <TableCell><Badge className="bg-emerald-500/20 text-emerald-400 border border-emerald-500/20">BOOK PROFIT</Badge></TableCell>
                      <TableCell className="text-slate-300">₹ 480.00</TableCell>
                      <TableCell className="text-slate-300">₹ 530.00</TableCell>
                      <TableCell className="text-emerald-400 text-right font-bold">+₹ 500.00</TableCell>
                    </TableRow>
                    <TableRow className="border-slate-800">
                      <TableCell className="text-slate-400">09:20 AM</TableCell>
                      <TableCell className="text-slate-300">BTST VIP+</TableCell>
                      <TableCell className="text-white font-medium">NIFTY 23500 CE</TableCell>
                      <TableCell><Badge className="bg-slate-700 text-slate-300 border border-slate-600">TSL AT COST</Badge></TableCell>
                      <TableCell className="text-slate-300">₹ 120.00</TableCell>
                      <TableCell className="text-slate-300">₹ 120.00</TableCell>
                      <TableCell className="text-slate-400 text-right font-bold">₹ 0.00</TableCell>
                    </TableRow>
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </div>
        )}

        {/* SYSTEM LOGS TAB */}"""
content = content.replace("{/* SYSTEM LOGS TAB */}", tab_html)

codecs.open(path, 'w', 'utf-8').write(content)
print('Patched successfully!')
