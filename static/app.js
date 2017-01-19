var min = false;

var colorMapping = {
    Creation: '#2ca02c',
    Party: '#7f7f7f',
    Context: '#8c564b',
    Place: '#17becf',
    Category: '#ff7f0e',
    Descriptor:  '#1f77b4',
    Link:  '#d62728',
    Quantity: '#bcbd22',
    Time: '#9467bd',
    Right: '#aec7e8',
    RightsAssignment: '#ff7f0e',
    Acknowledge: '#ffbb78',
    Pay: '#98df8a',
    'odrl:Set': '#1f77b4',
    'odrl:Duty': '#17becf',
    'odrl:Constraint': '#bcbd22',
    'odrl:Permission': '#2ca02c',
    'dcterms:DCMITypeText': '#f7b6d2',
    'chub:PersonalWebsiteAds': '#c7c7c7',
};
var reservedColors = [
  '#c49c94',
  '#9edae5',
  '#e377c2',
  '#dbdb8d',
  '#c5b0d5',
  '#ff9896',
];

colorMapping['*Untyped*'] = '#e377c2';

var docEl = document.documentElement,
    bodyEl = document.getElementsByTagName('body')[0];

var width = window.innerWidth || docEl.clientWidth || bodyEl.clientWidth,
    height =  window.innerHeight|| docEl.clientHeight|| bodyEl.clientHeight;

var force = d3.layout.force()
  .charge(-120)
  .linkDistance(45)
  .size([width, height]);

var zoom = d3.behavior.zoom()
  .scaleExtent([0.25, 20])
  .on("zoom", function() {
    container.attr(
      "transform",
      "translate(" + d3.event.translate + ")scale(" + d3.event.scale + ")");
  });

var svg = d3.select("body").append("svg")
  .attr("width", width)
  .attr("height", height)
  .append("g")
  .attr("transform", "translate(-5, -5)")
  .call(zoom);

svg.append("rect")
  .attr("width", "100%")
  .attr("height", "100%")
  .attr("fill", "#f8f8f8");

svg.append("text")
  .attr("x", (width / 2))
  .attr("y", 30)
  .attr("text-anchor", "middle")
  .style("font-size", "20px")
  .text('LCC Triples Visualisation');

var container = null;
var legend = null;
var color = null;
var data = null;

function reset() {
  if (container != null) {
    container.remove();
  }
  container = svg.append("g");
  if (legend != null) {
    legend.remove();
  }
  color = d3.scale.category10();
}

var lineFunction = d3.svg.line()
                         .x(function(d) { return d.x; })
                         .y(function(d) { return d.y; })
                         .interpolate("linear");

function addNodeTooltip(node, color) {
  var group = node.attr("group");
  var tooltip = node
    .append("text")
    .text(group + ': ' + node.attr("name"))
    .attr("x", -20)
    .attr("y", -10)
    .attr("id", "nodeTooltip")
    .style("font-size", "15px")
    .style("fill", colorMapping[group]);
}

function addLinkTooltip(link) {
  var tooltip = container
    .append("text")
    .attr("id", "linkTooltip")
    .style("font-size", "10px")
    .style("fill", '#999')
    .append("textPath")
    .attr("xlink:href", function(d,i) { return '#' + link.attr('id');})
    .text(link.attr('predicate'));
}

function plot(error, graph) {
  reset();

  data = graph;
  console.log(graph);

  force
    .nodes(graph.nodes)
    .links(graph.links)
    .alpha(.1)
    .start();

  container.append("defs").append("marker")
      .attr("id", "markerArrow")
      .attr("viewBox", "0 -5 10 10")
      .attr("refX", 5)
      .attr("markerWidth", 6)
      .attr("markerHeight", 6)
      .attr("orient", "auto")
    .append("path")
      .attr("d", "M0,-5L10,0L0,5")
      .style("fill", "#999");

  var link = container.selectAll(".link")
    .data(graph.links)
    .enter()
    .append("path")
    .attr("class", "link")
    .attr("id", function(d) {return d.source.id + d.target.id})
    .attr("predicate", function(d) {return d.predicate})
    .attr("marker-mid",  "url(#markerArrow)")
    .on("mouseover", function(d) { addLinkTooltip(d3.select(this)); })
    .on("mouseout", function(d) { d3.select("#linkTooltip").remove(); })
    .on("mousedown", function(d) { d3.event.stopPropagation(); })

  var node = container.selectAll(".node")
    .data(graph.nodes)
    .enter()
    .append("g")
    .attr("class", "node")
    .attr("group", function(d) { return d.group; })
    .attr("name", function(d) { return d.name; })
    .attr("id", function(d) { return d.id; });

  node.append("circle")
    .attr("r", 5)
    .style("fill", function(d) { return colorMapping[d.group]; })
    .call(force.drag)

  var labels = node.append("text")
    .attr("x", 12)
    .attr("y", ".35em")
    .text(function(d) { return d.name });

  node
    .on("mouseover", function(d) { addNodeTooltip(d3.select(this), color); })
    .on("mouseout", function(d) { d3.select("#nodeTooltip").remove(); })
    .on("mousedown", function(d) { d3.event.stopPropagation(); })
    

  force.on("tick", function() {
    link.attr("d", function(d) {return lineFunction(
      [{x: d.source.x, y: d.source.y}
       ,
       {x: (d.source.x + d.target.x) / 2, y: (d.source.y + d.target.y) / 2},
       {x: d.target.x, y: d.target.y}])});

    node
    .attr("cx", function(d) { return d.x; })
    .attr("cy", function(d) { return d.y; })
    .attr("transform", function(d) {
      return "translate(" + d.x + "," + d.y + ")"; });
  });


  legend = svg.selectAll(".legend")
    .data(Object.keys(colorMapping).filter(
      function(d) {
        presentGroups = graph.nodes.map(function(obj) {return obj.group});
        presentGroups = presentGroups.filter(
          function(value, index, self) {return self.indexOf(value) === index;})
        return presentGroups.indexOf(d) != -1}))
    .enter().append("g")
    .attr("class", "legend")
    .attr("transform", function(d, i) { return "translate(0," + i * 20 + ")"; });

  legend.append("rect")
    .attr("x", width - 50)
    .attr("y", 50)
    .attr("width", 18)
    .attr("height", 18)
    .style("fill", function(d) { return colorMapping[d]});

  legend.append("text")
    .attr("x", width - 54)
    .attr("y", 60)
    .attr("dy", ".35em")
    .style("text-anchor", "end")
    .style("font-size", "10px")
    .text(function(d) { return d; });
};


d3.select('#refresh').on('click', function() {
  force.resume();
});

function updateDoc() {
  var endpoint = min ? '/compress' : '/expand',
      request = new XMLHttpRequest();
  request.open("GET", endpoint);
  request.send();
  request.onload = function(e) {
    if (this.status == 200) {
      reset();
      plot('', this.response);
      transBtn.classed('fa-compress', !min);
      transBtn.classed('fa-expand', min);
    } else {
      alert(this.response['error']);
    }
  };
  request.responseType = 'json';
}

var transBtn = d3.select('#transform');
transBtn.on('click', function() {
  min = !min;
  updateDoc();
});

d3.select("#upload").on("click", function(){
  var elem = document.getElementById("hidden-file-upload");
  elem.value = '';
  elem.click();
});

d3.select("#hidden-file-upload").on("change", function(){
    if (window.File && window.FileReader && window.FileList && window.Blob) {
        var formData = new FormData();
        var file = this.files[0];
        formData.append('triples', file);
        formData.append('min', min);
        var request = new XMLHttpRequest();
        request.open("POST", "/render");
        request.send(formData);
        request.onload = function(e) {
          if (this.status == 200) {
            reset();
            plot('', this.response);
          } else {
            alert(this.response['error']);
          }
        };
        request.responseType = 'json';
      }
});

d3.select('#delete').on('click', function() {
  doReset = window.confirm("Press OK to delete this graph");
  if (doReset) {
    reset();
  }

})

updateDoc();
