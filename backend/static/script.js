document.getElementById('network-control-form').addEventListener('submit', async function(event) {
    event.preventDefault();
    const auditorium = document.getElementById('auditorium').value;
    const action = event.submitter.id;
    let url;

    if (action === 'turn-off') {
        url = '/turn_off_network/';
    } else if (action === 'turn-on') {
        url = '/turn_on_network/';
    } else if (action === 'check') {
        url = '/check_network/';
    }

    const response = await fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify({ number: auditorium })
    });

    const result = await response.json();
    document.getElementById('output').innerText = result.message + '\n' + result.output;
});
