var nodes = [
  {id: 4, label: 'Node 4'},
  {id: 5, label: 'Node 5'},
  {id: 6, label: 'Node 6', cid:1},
  {id: 7, label: 'Node 7', cid:1}
]

    // // create an array with nodes
    // var nodes = new vis.DataSet([
    //     {id: 1, label: 'Node 1'},
    //     {id: 2, label: 'Node 2'},
    //     {id: 3, label: 'Node 3'},
    //     {id: 4, label: 'Node 4'},
    //     {id: 5, label: 'Node 5'}
    // ]);

    var options = {
  joinCondition:function(nodeOptions) {
    return nodeOptions.cid === 1;
  }
}


    // create an array with edges
    var edges = new vis.DataSet([
        {from: 6, to: 4}, //from cid 1 to 4
        {from: 7, to: 5} //from cid 1 to 5
        // {from: 4, to: 5},
        // {from: 4, to: 6}
        // {from: 1, to: 5},
        // {from: 2, to: 4},
        // {from: 2, to: 5}
    ]);

    // create a network
    var container = document.getElementById('mynetwork');

    // provide the data in the vis format
    var data = {
        nodes: nodes,
        edges: edges
    };
    // var options = {};


    // initialize your network!
    var network = new vis.Network(container, data, options);
    network.clustering.cluster(options);