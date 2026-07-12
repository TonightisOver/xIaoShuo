/**
 * AI 职业生成预设数据
 *
 * 从 Careers.vue 提取的 4 类预设职业体系（修仙 / 武道 / 魔法 / 科技），
 * 每类含 10 个等级阶段。纯数据，无副作用，便于独立维护与扩展。
 */

export const CAREER_PRESETS = {
  修仙: {
    name: '大罗九天太乙仙',
    category: '修仙',
    description: '证道混元大罗，在灵气中参悟造化生死、虚空万界因果规则的至上修真天梯。',
    stages: [
      { level: 1, name: '凡砂蜕骨', description: '褪去一身凡俗骨血尘垢，吸纳天地第一缕玄清灵气。', breakthrough: '在清晨紫气东来之时盘坐洗髓。' },
      { level: 2, name: '九宫灵旋', description: '在腹中气海开拓出九个小灵旋，源源不断吞吐大荒气息。', breakthrough: '破入灵髓池浸泡半日。' },
      { level: 3, name: '玄胎筑基', description: '灵气化液，汇入仙脉，筑造出支撑万载寿元的琉璃玄台。', breakthrough: '服下一颗极品筑基丹并心境通透。' },
      { level: 4, name: '紫金结丹', description: '灵台雷霆闪烁，孕育出一枚照耀百里的紫金不灭金丹。', breakthrough: '在无上聚灵大阵中经受天劫余威。' },
      { level: 5, name: '真命元神', description: '粉碎金丹，温养出不堕虚空的元神，精神力可瞬息扫过山河。', breakthrough: '元神突破魂海束缚，历经地心罡风淬洗。' },
      { level: 6, name: '万法化身', description: '元神化为九种极道仙光，拥有断肢重生、移山填海的莫大神通。', breakthrough: '炼化一件本命灵虚法宝。' },
      { level: 7, name: '诸界洞天', description: '神识在体内开辟出微型乾坤，可凭空储物或演化万物灵力。', breakthrough: '融合一片残存的破碎仙界洞天。' },
      { level: 8, name: '无极太乘', description: '参悟天地自然造化无为，举手投足自带法则压迫，震慑四野。', breakthrough: '枯坐百年了却红尘宿愿。' },
      { level: 9, name: '乾坤道劫', description: '斩却三尸，直面天地法则的大破灭风水火土混元四九神雷。', breakthrough: '依靠自身坚毅不灭的意志硬抗道劫。' },
      { level: 10, name: '太乙金仙', description: '白日飞升，跳出三界外，不在五行中，证得太乙金仙道果。', breakthrough: '登天路，斩断因果锁链。' },
    ],
  },
  武道: {
    name: '万劫真龙武神',
    category: '武道',
    description: '极致磨砺肉身极限，开辟体内十万神藏，以气血真意打破粉碎真空的无双纯肉身战斗神话。',
    stages: [
      { level: 1, name: '磐石骨骼', description: '骨髓如汞，骨骼粗壮坚硬胜过百炼精钢，肉身力负千斤。', breakthrough: '浸泡九窍药水，锤炼筋骨百日。' },
      { level: 2, name: '惊雷真劲', description: '气血于肌肉之中震荡，产生如雷鸣般的刚猛爆发暗劲。', breakthrough: '击断瀑布十丈，领悟爆发暗劲。' },
      { level: 3, name: '气海沸腾', description: '气血如惊涛骇浪，开辟中丹田武道气海，真气能外放三丈。', breakthrough: '击杀一头一阶凶兽并吞食其气血精元。' },
      { level: 4, name: '琉璃金身', description: '肌肤亮如琉璃，内脏强劲，刀枪不入，寻常水火兵刃难伤分毫。', breakthrough: '经受熔火真铁砂捶打七天七夜。' },
      { level: 5, name: '五脏神光', description: '心肝脾肺肾孕育出五行神光，生机断续，心脏受创亦能短时自愈。', breakthrough: '吞噬一枚五行奇珍天心草。' },
      { level: 6, name: '通达造化', description: '武道感悟融入气血，举手投足皆合乎武道至理，真气生生不息。', breakthrough: '与同阶武者鏖战三天三夜，突破心障。' },
      { level: 7, name: '碎空法体', description: '举手投足间空气开裂，纯肉身速度超越音速，产生震荡虚空的裂音。', breakthrough: '在重力极高的地磁深渊修行七日。' },
      { level: 8, name: '滴血重生', description: '生命元能浓郁到每一滴鲜血中都蕴含着极强意志，断手一息可续。', breakthrough: '涅槃熔炉之火淬炼，死里逃生。' },
      { level: 9, name: '粉碎真空', description: '打破天地屏障的绝对唯物压制，纯物理重拳可以直接砸裂虚空。', breakthrough: '挥出十万八千重拳，打破法则重压。' },
      { level: 10, name: '真龙武神', description: '肉身跨越纪元而永生，凝练不朽真龙神格，宇宙崩塌唯肉体长存。', breakthrough: '将体内十万八千神藏与宇宙星空连通。' },
    ],
  },
  魔法: {
    name: '奥术编织主宰',
    category: '魔法',
    description: '掌握构成多元宇宙的秩序、混沌、水、火、风、土等纯元素魔力符号，以真理编织奥术世界的法则君主。',
    stages: [
      { level: 1, name: '冥想学徒', description: '能在灵魂深处观想魔力光点，并勉强画出单字魔力符文。', breakthrough: '成功点亮第一枚灵识魔力符咒。' },
      { level: 2, name: '低阶法士', description: '可凝聚出火球、水弹等基础元素具象，精神力足支持数轮施法。', breakthrough: '独自完成一次实战施法历练。' },
      { level: 3, name: '魔导专精', description: '在某一元素或奥术领域极其专精，能够默发三环以下所有法术。', breakthrough: '通过法师工会考核，成功精炼魔力。' },
      { level: 4, name: '魔力泉涌', description: '法术海无间断爆发，可以在精神海形成永动回蓝泉眼，极大提高爆发。', breakthrough: '融合一颗中阶魔核并建立体内回路。' },
      { level: 5, name: '天灾大巫', description: '能够吟唱大范围灾厄级法术，如陨石天降或暴风雪降临。', breakthrough: '抗衡并驯服一只高阶魔能元素兽。' },
      { level: 6, name: '传奇贤者', description: '洞悉元素本质，甚至能利用魔力在自身周围构建传奇豁免结界。', breakthrough: '在古老真理遗迹感悟魔力之源。' },
      { level: 7, name: '空间旅者', description: '精通时空编织，能够随心所欲跨越百里闪烁，甚至开启界域之门。', breakthrough: '掌握星轨逆转方程式并稳定穿梭空间。' },
      { level: 8, name: '法则禁咒尊', description: '能施展毁灭城池与改变气候格局的灭世禁咒，引动星空魔法狂潮。', breakthrough: '炼制一把属于自己的禁咒级法则权杖。' },
      { level: 9, name: '神格点燃', description: '将奥术本源铭刻在灵魂深处，神识在奥术星河中获得属于自己的坐标。', breakthrough: '汇聚庞大信仰之力，点燃神火。' },
      { level: 10, name: '奥术主宰', description: '意志即是魔法界的最高铁律，一言即出元素重组，真理彻底掌握在手。', breakthrough: '将魔网节点彻底接入自身意志中。' },
    ],
  },
  科技: {
    name: '序列超脑掌控者',
    category: '科技',
    description: '开发脑域至 100% 极限，将肉身及意志尽皆降维信息流并掌握机械科技绝对真理的先驱者。',
    stages: [
      { level: 1, name: '微光接口', description: '在后脑成功植入神经芯片，可通过意念直接和普通终端实现信息互联。', breakthrough: '顺利通过信息交互压力测试。' },
      { level: 2, name: '超感神经', description: '五感敏锐度提升五倍，脑电波可形成实体微弱念力，能隔空移物。', breakthrough: '植入超感纳米机群。' },
      { level: 3, name: '初级超脑', description: '脑域开发达到20%，心算速度比拟普通电脑，可侵入并接管民用局域网络。', breakthrough: '融合外载算力阵列。' },
      { level: 4, name: '念力具象', description: '脑力高度实质化，可以用念力硬抗轻型机枪扫射，并在体外凝结屏障。', breakthrough: '突破四维认知屏障。' },
      { level: 5, name: '天网节点', description: '能够将自身脑波投射进全球网络，化为天网算法的一部分，操纵无人机群。', breakthrough: '成功上传1TB个人逻辑数据。' },
      { level: 6, name: '智囊先驱', description: '脑域开发45%，能够自主预判战场三秒内的任意弹道与攻势，绝对掌控。', breakthrough: '通过智库终极心智考核。' },
      { level: 7, name: '量子拟合', description: '脑域完全实现量子运算，可模拟演化分子级物质重组，凭空操控机械。', breakthrough: '吸收星核量子源。' },
      { level: 8, name: '机械先驱', description: '可以随时接管大型歼星舰或者星际防线的核心主脑，掌控千亿级机械军团。', breakthrough: '将肉身半数转为超导纳米合金。' },
      { level: 9, name: '高维幽灵', description: '摆脱碳基肉身依赖，意志融入全宇宙的量子波谱中，无处不在。', breakthrough: '主脑全面云端化，超脱生死。' },
      { level: 10, name: '神念造物主', description: '掌握科技法则最高真理，单凭宏大算法意识便可瞬息编织、捏造或湮灭星体。', breakthrough: '宇宙基本力信息逻辑公式完美融汇。' },
    ],
  },
}

/**
 * 根据 category 获取预设职业（修仙/武道/魔法/科技）。
 * 未知 category 回退到「科技」预设。
 * 返回深拷贝对象（含 stages 数组），调用方修改不会污染原预设数据。
 * 返回对象不含 id（调用方负责赋值，因为依赖 Date.now()）。
 */
export function getPresetCareer(category) {
  const preset = CAREER_PRESETS[category] || CAREER_PRESETS.科技
  // 深拷贝 stages，避免调用方修改污染预设常量
  return {
    ...preset,
    category: preset.category,
    stages: preset.stages.map((s) => ({ ...s })),
  }
}
