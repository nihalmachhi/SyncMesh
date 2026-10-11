from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle, Flowable
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from pathlib import Path

OUT=Path("docs/SyncMesh_How_It_Works.pdf")
OUT.parent.mkdir(parents=True,exist_ok=True)
INK=colors.HexColor("#203137"); TEAL=colors.HexColor("#176F63"); MINT=colors.HexColor("#E9F3F0")
MUTED=colors.HexColor("#68797D"); LINE=colors.HexColor("#DDE6E4"); PALE=colors.HexColor("#F5F8F7")
styles=getSampleStyleSheet()
styles.add(ParagraphStyle(name="CoverTitle",parent=styles["Title"],fontName="Helvetica-Bold",fontSize=27,leading=32,textColor=INK,alignment=TA_LEFT,spaceAfter=8))
styles.add(ParagraphStyle(name="Deck",parent=styles["Normal"],fontSize=12,leading=18,textColor=MUTED,spaceAfter=16))
styles.add(ParagraphStyle(name="H",parent=styles["Heading2"],fontName="Helvetica-Bold",fontSize=16,leading=20,textColor=TEAL,spaceBefore=8,spaceAfter=8))
styles.add(ParagraphStyle(name="Body2",parent=styles["BodyText"],fontSize=10.2,leading=15,textColor=INK,spaceAfter=7))
styles.add(ParagraphStyle(name="Small2",parent=styles["BodyText"],fontSize=8.5,leading=12,textColor=MUTED))
styles.add(ParagraphStyle(name="Step",parent=styles["BodyText"],fontSize=9.4,leading=14,textColor=INK))
class FlowDiagram(Flowable):
 def __init__(self,mode="write"): Flowable.__init__(self); self.mode=mode; self.width=170*mm; self.height=65*mm
 def draw(self):
  c=self.canv
  if self.mode=="write":
   boxes=[("React UI",8,42),("FastAPI node",62,42),("SQLite log",116,42),("Peer node",116,8)]
   for label,x,y in boxes:
    c.setFillColor(MINT if label!="Peer node" else PALE); c.setStrokeColor(LINE); c.roundRect(x*mm,y*mm,40*mm,15*mm,3*mm,fill=1,stroke=1)
    c.setFillColor(INK); c.setFont("Helvetica-Bold",9); c.drawCentredString((x+20)*mm,(y+6)*mm,label)
   c.setStrokeColor(TEAL); c.setLineWidth(1.5)
   for x1,y1,x2,y2 in [(48,49.5,62,49.5),(102,49.5,116,49.5),(136,42,136,23)]:
    c.line(x1*mm,y1*mm,x2*mm,y2*mm); c.line((x2-2)*mm,(y2+2)*mm,x2*mm,y2*mm); c.line((x2-2)*mm,(y2-2)*mm,x2*mm,y2*mm)
   c.setFillColor(MUTED); c.setFont("Helvetica",8)
   c.drawCentredString(82*mm,35*mm,"durable local write")
   c.drawCentredString(145*mm,31*mm,"anti-entropy")
  else:
   labels=[("Node A","SQLite A"),("Node B","SQLite B"),("Node C","SQLite C")]
   for i,(node,db) in enumerate(labels):
    x=9+i*54
    c.setFillColor(MINT); c.setStrokeColor(LINE); c.roundRect(x*mm,29*mm,40*mm,25*mm,3*mm,fill=1,stroke=1)
    c.setFillColor(TEAL); c.setFont("Helvetica-Bold",9); c.drawCentredString((x+20)*mm,44*mm,node)
    c.setFillColor(INK); c.setFont("Helvetica",8); c.drawCentredString((x+20)*mm,36*mm,db)
   c.setStrokeColor(TEAL); c.setLineWidth(1.2)
   for x1,x2 in [(49,63),(103,117)]:
    c.line(x1*mm,41*mm,x2*mm,41*mm)
    c.line((x2-2)*mm,43*mm,x2*mm,41*mm); c.line((x2-2)*mm,39*mm,x2*mm,41*mm)
   c.setFont("Helvetica",8); c.setFillColor(MUTED); c.drawCentredString(82*mm,15*mm,"Exchange only operations missing from each peer")
def footer(canvas,doc):
 canvas.saveState(); w,h=A4
 canvas.setStrokeColor(LINE); canvas.line(18*mm,15*mm,w-18*mm,15*mm)
 canvas.setFont("Helvetica",8); canvas.setFillColor(MUTED)
 canvas.drawString(18*mm,10*mm,"SYNC MESH  |  LEARNING GUIDE")
 canvas.drawRightString(w-18*mm,10*mm,str(doc.page))
 canvas.restoreState()
doc=SimpleDocTemplate(str(OUT),pagesize=A4,rightMargin=19*mm,leftMargin=19*mm,topMargin=18*mm,bottomMargin=21*mm,title="SyncMesh - How It Works")
story=[]
story += [Spacer(1,14*mm),Paragraph("SyncMesh",styles["CoverTitle"]),Paragraph("How offline inventory changes move across independent stores",styles["Deck"])]
badge=Table([[Paragraph("<b>ONE NODE</b><br/>one private SQLite database",styles["Step"]),Paragraph("<b>ONE LOG</b><br/>immutable ordered operations",styles["Step"]),Paragraph("<b>ONE GOAL</b><br/>replicas converge when connected",styles["Step"])]],colWidths=[55*mm]*3)
badge.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),PALE),("BOX",(0,0),(-1,-1),0.6,LINE),("INNERGRID",(0,0),(-1,-1),0.5,LINE),("VALIGN",(0,0),(-1,-1),"MIDDLE"),("LEFTPADDING",(0,0),(-1,-1),9),("RIGHTPADDING",(0,0),(-1,-1),9),("TOPPADDING",(0,0),(-1,-1),10),("BOTTOMPADDING",(0,0),(-1,-1),10)]))
story += [badge,Spacer(1,12*mm),Paragraph("The core idea",styles["H"]),Paragraph("A shop must keep working when the network is unavailable. SyncMesh commits each change to that shop's own database first. A background exchange sends missing changes to peers when a connection returns. The shared state emerges from exchanging operations; there is no central database.",styles["Body2"]),FlowDiagram("write"),Paragraph("A single change, end to end",styles["H"])]
rows=[[Paragraph("<b>1. React dashboard</b><br/>The operator creates or adjusts inventory at the selected location.",styles["Step"])],[Paragraph("<b>2. FastAPI node</b><br/>The API validates the request and records an immutable operation.",styles["Step"])],[Paragraph("<b>3. SQLite transaction</b><br/>The operation log and local inventory view are updated durably.",styles["Step"])],[Paragraph("<b>4. Peer exchange</b><br/>When online, the node compares vectors and sends missing operations.",styles["Step"])]]
t=Table(rows,colWidths=[165*mm]); t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),colors.white),("LINEBELOW",(0,0),(-1,-2),0.5,LINE),("LEFTPADDING",(0,0),(-1,-1),8),("TOPPADDING",(0,0),(-1,-1),7),("BOTTOMPADDING",(0,0),(-1,-1),7)]));story += [t,PageBreak()]
story += [Paragraph("How replicas catch up",styles["CoverTitle"]),Paragraph("Three nodes keep their own histories and compare progress before transferring data.",styles["Deck"]),FlowDiagram("nodes"),Paragraph("Operation identity and vector clocks",styles["H"]),Paragraph("Each operation carries an origin node ID and a sequence number, such as <b>shop-a:12</b>. A version vector such as <b>{shop-a: 12, shop-b: 4}</b> records the highest contiguous sequence applied from each origin. If sequence 12 arrives before 11, it waits in the pending queue until the gap closes. Duplicate operation IDs are ignored.",styles["Body2"]),Paragraph("Conflict behavior",styles["H"])]
data=[[Paragraph("<b>Change</b>",styles["Step"]),Paragraph("<b>Rule</b>",styles["Step"])],[Paragraph("Causally ordered field edit",styles["Step"]),Paragraph("An edit that knows the prior version supersedes it.",styles["Step"])],[Paragraph("Concurrent field edits",styles["Step"]),Paragraph("Compare UTC timestamps; node ID and operation ID break ties.",styles["Step"])],[Paragraph("Stock adjustment",styles["Step"]),Paragraph("Add signed deltas. Concurrent -2 and -3 changes total -5.",styles["Step"])],[Paragraph("Delete",styles["Step"]),Paragraph("Keep a tombstone so an older copy cannot revive the item.",styles["Step"])]]
tb=Table(data,colWidths=[56*mm,109*mm]);tb.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),MINT),("GRID",(0,0),(-1,-1),0.5,LINE),("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),8),("TOPPADDING",(0,0),(-1,-1),8),("BOTTOMPADDING",(0,0),(-1,-1),8)]));story += [tb,Spacer(1,6*mm),Paragraph("Run the demo",styles["H"]),Paragraph("1. Install Docker Desktop and wait for its engine to start.<br/>2. In the project folder run <b>docker compose up --build</b>.<br/>3. Open <b>http://localhost:5173</b> and add an inventory item.<br/>4. Select another node card and inspect its replica. Use <b>Sync now</b> to request an exchange.<br/>5. Stop with Ctrl+C. Use <b>docker compose down -v</b> only when you intend to erase the demo databases.",styles["Body2"]),PageBreak()]
story += [Paragraph("Project map and learning path",styles["CoverTitle"]),Paragraph("Follow one request through the folders to understand where each responsibility belongs.",styles["Deck"])]
rows=[[Paragraph("<b>Folder</b>",styles["Step"]),Paragraph("<b>Purpose</b>",styles["Step"])],[Paragraph("src/syncmesh/protocol",styles["Step"]),Paragraph("Operation messages and version-vector math.",styles["Step"])],[Paragraph("src/syncmesh/node/api",styles["Step"]),Paragraph("FastAPI request and WebSocket boundaries.",styles["Step"])],[Paragraph("src/syncmesh/node/services",styles["Step"]),Paragraph("Peer synchronization use case.",styles["Step"])],[Paragraph("src/syncmesh/node/storage",styles["Step"]),Paragraph("SQLite lifecycle, schema, operation log, pending queue.",styles["Step"])],[Paragraph("frontend/src",styles["Step"]),Paragraph("React Router dashboard and replica views.",styles["Step"])],[Paragraph("tests",styles["Step"]),Paragraph("Focused correctness checks for repository and vector behavior.",styles["Step"])]]
tb=Table(rows,colWidths=[60*mm,105*mm]);tb.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),MINT),("GRID",(0,0),(-1,-1),0.5,LINE),("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),8),("TOPPADDING",(0,0),(-1,-1),8),("BOTTOMPADDING",(0,0),(-1,-1),8)]));story += [tb,Paragraph("Try these experiments",styles["H"]),Paragraph("<b>Offline write:</b> stop node-b, add an item on node-a, restart node-b, then compare item counts.<br/><b>Stock merge:</b> after syncing an item, adjust stock at two nodes before the next exchange. Additive deltas commute.<br/><b>Inspect progress:</b> open /sync/vector and /stats on ports 8001-8003 to read vector clocks and operation counts.",styles["Body2"]),Paragraph("Prototype limitations",styles["H"]),Paragraph("This project is an educational prototype. It does not provide authentication, encrypted transport, peer discovery, operation-log compaction, or production-grade conflict review. Keep demo endpoints on a trusted local network. The demo contains no measured performance claims.",styles["Body2"])]
doc.build(story,onFirstPage=footer,onLaterPages=footer)
print(OUT.resolve())


