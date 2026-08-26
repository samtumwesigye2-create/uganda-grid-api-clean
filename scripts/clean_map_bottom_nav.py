from pathlib import Path
p=Path('index.html')
s=p.read_text(encoding='utf-8')
# These three dashboard buttons only set visual active state in index.html and
# have no action/overlay handler in app.js. Remove them from the map dashboard.
for html in [
'<button class="navTab" id="tabShip"><span class="tabIcon">&#128230;</span>Ship</button>\n',
'<button class="navTab" id="tabCommercial"><span class="tabIcon">&#127970;</span>Commercial</button>\n',
'<button class="navTab" id="tabAdmin"><span class="tabIcon">&#128272;</span>Admin</button>\n'
]:
    s=s.replace(html,'')
s=s.replace("var tabs = ['tabHome','tabAddress','tabSaved','reportBtn','tabShip','tabCommercial','tabAdmin','tabMore'];",
            "var tabs = ['tabHome','tabAddress','tabSaved','reportBtn','tabMore'];")
# Remove the no-op listeners as well.
blocks=[
"""var shipBtn = document.getElementById('tabShip');
if (shipBtn) shipBtn.addEventListener('click', function () { setActiveTab('tabShip'); });

""",
"""var commercialBtn = document.getElementById('tabCommercial');
if (commercialBtn) commercialBtn.addEventListener('click', function () { setActiveTab('tabCommercial'); });

""",
"""var adminBtn = document.getElementById('tabAdmin');
if (adminBtn) adminBtn.addEventListener('click', function () { setActiveTab('tabAdmin'); });

"""
]
for b in blocks:s=s.replace(b,'')
p.write_text(s,encoding='utf-8')
