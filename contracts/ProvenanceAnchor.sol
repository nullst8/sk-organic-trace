// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract ProvenanceAnchor {
    mapping(uint256 => bytes32) public roots;
    uint256 public count;

    event Anchored(uint256 indexed id, bytes32 root, uint256 timestamp);

    function anchor(bytes32 root) external {
        roots[count] = root;
        emit Anchored(count, root, block.timestamp);
        count++;
    }
}
