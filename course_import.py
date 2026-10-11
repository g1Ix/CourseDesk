import re
from collections import defaultdict
from datetime import date,timedelta
PERIODS=14
def _compact_ocr(value: str) -> str:
    return re.sub(r"\s+", "", value).replace("．", "·").replace("。", "·")


def _ocr_course_fields(lines: list[dict]) -> tuple[str, str, str]:
    text = _compact_ocr("".join(line.get("text", "") for line in lines))
    room_match = re.search(r"@\s*([A-Za-z0-9]{2,})", text)
    if not room_match:
        room_match = re.search(r"(?<![A-Za-z0-9])(0[0-9A-Za-z]{3,6})(?![A-Za-z0-9])", text)
    room = room_match.group(1).upper() if room_match else ""
    title_line = text.split("@")[0]
    if room_match:
        title_line = title_line.replace(room_match.group(0), "")
    role = r"(?:主讲|主講|主训|主訓|庄训|講|讲|训|訓|授课|授課|教师|老師|老师|主)$"
    suffix_match = re.search(role, title_line)
    if suffix_match:
        # Some screenshots omit punctuation between the course and instructor.
        head = title_line[:suffix_match.start()]
        split_match = re.match(r"(.+)([\u4e00-\u9fff]{3})$", head)
        if not split_match:
            split_match = re.match(r"(.+)([\u4e00-\u9fff]{2})$", head)
        if split_match:
            title_line = split_match.group(1) + "·" + split_match.group(2)
        else:
            title_line = head
    title_line = re.sub(r"(?:\[|【)?(?:主讲|主講|主训|主訓|庄训|讲|講|授课|授課|教师|老師|老师|主)(?:\]|】)?", "", title_line)
    title_line = re.sub(r"\d{1,2}月|第\d+周|课表查询|課表查詢", "", title_line)
    parts = re.split(r"[-—–_一卜:：·]", title_line, maxsplit=1)
    if len(parts) == 2:
        course, teacher = parts[0], parts[1]
    else:
        course, teacher = title_line, ""
    course = re.sub(r"[\[\]【】()（）《》]", "", course).strip("·．。，,[]【】主讲講")
    teacher = re.sub(r"\(.*$|（.*$", "", teacher)
    teacher = re.sub(r"(?:主讲|主講|主训|主訓|庄训|讲|講|训|訓|授课|授課|老师|教师).*$", "", teacher)
    teacher = re.sub(r"[\[\]【】()（）《》]", "", teacher).strip("·．。，,[]【】主讲講训庄一卜")
    if not course:
        course = text.split("@")[0].strip("·．。，,[]【】主讲講") or "待校对课程"
    return course, teacher, room


def ocr_pages_to_rows(payload: dict, default_weeks: list[int], per_week: bool, first_week: int = 1, term_start: str | None = None) -> list[dict]:
    pages = payload.get("pages", [])
    explicit_weeks = []
    for page in pages:
        text = "".join(_compact_ocr(str(line.get("text", ""))) for line in page.get("lines", []))
        match = re.search(r"第\s*(\d+)\s*周", text)
        explicit_weeks.append(int(match.group(1)) if match else None)
    detected_first = next((w for w in explicit_weeks if w is not None), None)
    week_offset = first_week - 1
    rows = []
    for page_index, page in enumerate(pages):
        lines = page.get("lines", [])
        width, height = float(page.get("width", 0)), float(page.get("height", 0))
        if width <= 0 or height <= 0:
            continue
        week = explicit_weeks[page_index]
        if week is None and detected_first is not None:
            week = detected_first + page_index
        if week is not None:
            week -= week_offset
        start=date.fromisoformat(term_start) if term_start else None
        start_monday=start-timedelta(days=start.weekday()) if start else None
        header_dates={}
        compact_lines=[(line,_compact_ocr(line.get('text',''))) for line in lines]
        weekday_names='一二三四五六日'
        anchors=[]
        for line,txt in compact_lines:
            match=re.fullmatch(r'(?:周|星期)([一二三四五六日天])',txt)
            if match:anchors.append((weekday_names.index(match[1].replace('天','日')),float(line['x'])+float(line.get('width',0))/2,float(line['y'])+float(line.get('height',0))/2))
        # Infer the weekday grid from recognized labels; reject unrelated documents.
        if len(anchors)<2:continue
        slopes=[(b[1]-a[1])/(b[0]-a[0]) for a in anchors for b in anchors if b[0]>a[0]]
        if not slopes:continue
        column_width=sorted(slopes)[len(slopes)//2]
        if column_width<=0:continue
        centers=[x-dow*column_width for dow,x,y in anchors];first_center=sorted(centers)[len(centers)//2];left=first_center-column_width/2
        header_y=sum(y for _,_,y in anchors)/len(anchors)
        periods=[]
        for line,txt in compact_lines:
            match=re.fullmatch(r'(1[0-4]|[1-9])节',txt)
            if match and float(line['x'])<left:periods.append((int(match[1]),float(line['y'])+float(line.get('height',0))/2))
        if len(periods)>=2:
            slopes=[(yb-ya)/(b-a) for a,ya in periods for b,yb in periods if b>a];period_height=sorted(slopes)[len(slopes)//2];grid_top=sum(y-(n-.5)*period_height for n,y in periods)/len(periods);pair_height=period_height*2
        else:
            # Text-only PDFs may omit the period labels. Keep the recognizable day grid,
            # but the proposed two-period blocks must be checked in the preview.
            grid_top=header_y+height*.06;pair_height=(height-grid_top)/4
        if start:
            months=[int(m[1]) for line,txt in compact_lines if (m:=re.fullmatch(r'(\d{1,2})月',txt)) and float(line['y'])<grid_top]
            month=months[0] if months else None
            for line,txt in compact_lines:
                x=float(line['x'])+float(line.get('width',0))/2;y=float(line['y'])
                if month and txt.isdigit() and 1<=int(txt)<=31 and header_y<y<grid_top and x>=left:
                    dow=max(0,min(6,round((x-first_center)/column_width)))
                    choices=[]
                    for year in (start.year,start.year+1):
                        try:
                            day=date(year,month,int(txt))
                            if day.weekday()==dow and start_monday<=day<=start_monday+timedelta(days=735):choices.append(day)
                        except ValueError:pass
                    if choices:header_dates[dow]=min(choices)
            if header_dates:
                known_day=next(iter(header_dates.values()));week=(known_day-timedelta(days=known_day.weekday())-start_monday).days//7+1
                origin=known_day-timedelta(days=known_day.weekday())
                header_dates={i:origin+timedelta(days=i) for i in range(7)}
        page_weeks = ([week] if week is not None else [default_weeks[min(page_index,len(default_weeks)-1)]]) if per_week and default_weeks else list(default_weeks)
        if not page_weeks:
            continue

        cells: dict[tuple[int, int], list[dict]] = defaultdict(list)
        for line in lines:
            x, y = float(line.get("x", 0)), float(line.get("y", 0))
            txt = str(line.get("text", "")).strip()
            if not txt or y < grid_top or y > height * 0.93 or x < left:
                continue
            col = max(0, min(6, int((x + float(line.get("width", 0)) / 2 - left) / column_width)))
            row = max(0, min(6, int((y - grid_top) / pair_height)))
            cells[(col, row)].append(line)

        contrast_cells=defaultdict(list)
        for line in page.get('contrast_lines',[]):
            x,y=float(line.get('x',0)),float(line.get('y',0))
            if y<grid_top or y>height*.93 or x<left:continue
            col=max(0,min(6,int((x+float(line.get('width',0))/2-left)/column_width)));slot=max(0,min(6,int((y-grid_top)/pair_height)));contrast_cells[(col,slot)].append(line)
        for cell,extra in contrast_cells.items():
            current=cells.get(cell,[])
            # OCR often reads white course titles only after contrast conversion.
            if not current or min(float(x['y']) for x in current)-min(float(x['y']) for x in extra)>pair_height*.08:
                title_lines=[x for x in extra if float(x['y'])<min((float(y['y']) for y in current),default=height)-10]
                cells[cell]=title_lines+current if current else extra

        for (weekday, row_slot), cell_lines in sorted(cells.items()):
            cell_lines.sort(key=lambda x:(round(float(x['y'])/10),float(x['x'])))
            combined = _compact_ocr("".join(str(x.get("text", "")) for x in cell_lines))
            # Ignore footer navigation and date/header text mistakenly captured below the grid.
            if not combined or "日历课" in combined or "星期课" in combined:
                continue
            course, teacher, room = _ocr_course_fields(cell_lines)
            if course in {"", "课", "讲", "主讲"} and not room:
                continue
            if len(re.sub(r'[^\u4e00-\u9fffA-Za-z]','',course))<3:course='待校对课程'
            first_period = row_slot * 2 + 1
            rows.append({"weekday": weekday, "period_start": first_period,
                         "period_end": min(PERIODS, first_period + 1), "course": course,
                         "teacher": teacher, "room": room, "weeks": page_weeks,
                         "_dates":[str(header_dates[weekday])] if weekday in header_dates and per_week else []})
    merged: dict[tuple, dict] = {}
    for row in rows:
        key = (row["weekday"], row["period_start"], row["period_end"], row["course"], row["teacher"], row["room"])
        if key not in merged:
            merged[key] = row
        else:
            merged[key]["weeks"] = sorted(set(merged[key]["weeks"] + row["weeks"]))
            merged[key]['_dates']=sorted(set(merged[key]['_dates']+row['_dates']))
    result=[]
    for row in merged.values():
        dates=row.pop('_dates',[])
        if len(row['weeks'])==1 and len(dates)==1:row['date']=dates[0];row.pop('weekday');row.pop('weeks')
        result.append(row)
    return result
