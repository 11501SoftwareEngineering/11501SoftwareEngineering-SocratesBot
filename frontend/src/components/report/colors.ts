/** 觀點群組的顏色（甜甜圈圖、群組卡片的圓點），照 Figma P13-1 的順序 */
const GROUP_COLORS = ['#8EB8B1', '#D29E97', '#91A8C4', '#B5AE9F', '#D4C9BA', '#A7C4A0']

export function groupColor(index: number) {
  return GROUP_COLORS[index % GROUP_COLORS.length]!
}
