pragma solidity ^0.8.0;

contract MempoolChallenge {
    address public owner;
    address public studentAddress;
    string private flag; 
    bool public revealed;
    
    bytes32 public constant targetHash = 0xd781033f8619ec5d3ab5387d3ad9b87203acce775bc100b32bfbac009e596cd6;

    event FlagRevealed(string flag);

    constructor(string memory _flag, address _studentAddress) {
        owner = msg.sender;
        flag = _flag;
        studentAddress = _studentAddress; 
        revealed = false;
    }

    function solve(string memory solution) public {
        require(!revealed, "Challenge already solved!");
        require(keccak256(abi.encodePacked(solution)) == targetHash, "Incorrect solution!");

        require(msg.sender == studentAddress, "Only the student can claim the flag!");

        revealed = true;
        emit FlagRevealed(flag);
    }

    function getFlag() public view returns (string memory) {
        require(revealed, "Challenge not yet solved!");
        return flag;
    }
}